# Pitfalls Research

**Domain:** TTL cascade over Redis (RedisJSON + Lua) across ForeignKey relationships in the `rapyer` ORM
**Researched:** 2026-07-06
**Confidence:** HIGH (Redis Cluster / replication / Lua-determinism claims verified against redis.io docs and Redis source discussions; codebase-specific claims verified against `rapyer/base.py`, `rapyer/config.py`, `rapyer/scripts/registry.py`, CONCERNS.md, CHANGELOG.md)

## Governing Tension (read first)

Every pitfall below is downstream of one structural fact: **the child keys a TTL cascade must touch are discovered by following FK pointers that live inside the parent's RedisJSON document — so they are NOT known at call time and cannot be pre-declared in `KEYS[]`.** This creates a trilemma between the three project constraints:

- **Atomic + server-side** → do the whole traversal inside one Lua script. But then child keys are discovered *inside* the script, violating the "all accessed keys must be in `KEYS[]`" rule (breaks Redis Cluster hard, and is officially unsupported for replication/AOF correctness).
- **Cluster/replication-correct** → pass every touched key in `KEYS[]`. But you can't know the keys until you've resolved the graph, which forces a multi-round-trip Python resolution phase → reintroduces TOCTOU (non-atomic).
- **Simple** → Python resolves the graph, then one `EXPIRE`-many pipeline. Loses both atomicity and (in cluster) cross-slot safety.

The roadmap's first cascade phase MUST pick a point in this trilemma explicitly (PROJECT.md already flags this as "Defer to research" in Key Decisions). Recommended default: **server-side Lua traversal, standalone-Redis-only, with a documented "not Cluster-safe" boundary** — because rapyer today is single-connection (`DEFAULT_CONNECTION`, tests run one `redis-stack-server`) and atomicity is the stated #1 constraint. Everything else in this document assumes that choice and warns where it bites.

## Critical Pitfalls

### Pitfall 1: Multi-round-trip Python traversal silently breaks the atomicity guarantee

**What goes wrong:**
The "simple" implementation resolves the FK graph in Python — `aget` parent, read FK key strings, `aget` each child, recurse — accumulating a key list, then issues one `EXPIRE` pipeline. Between the first read and the final `EXPIRE`, any child can be deleted, overwritten with a new FK target, or have its own TTL expire. The cascade then either expires a stale set of keys, misses a newly-linked child, or sets TTL on a key that no longer exists. The single-MULTI/EXEC `EXPIRE` at the end *looks* atomic but the read-and-branch traversal that produced its key list was not.

**Why it happens:**
The project's own machinery makes this the path of least resistance: `ForeignKey.afetch()` is already lazy and per-instance, transactional pipelines "cannot read-then-branch mid-transaction" (PROJECT.md), and the N+1 FK-resolution note in CONCERNS.md means developers will reach for a Python loop. The atomic seam (`ensure_pipeline`) genuinely cannot do the conditional traversal, so the traversal leaks out of the transaction.

**How to avoid:**
Do the traversal *inside* a single Lua script (`EVALSHA`) so the entire read-discover-branch-`EXPIRE` sequence is one server-side unit — Redis conceptually freezes time and key expiry for the script's duration (verified: "during Lua scripts executions no key expiries are performed... conceptually the time in the master is frozen"). If a Python-resolution design is chosen instead, it is NOT atomic and that must be stated as an accepted limitation, not hidden.

**Warning signs:**
A cascade code path that calls `afetch()`/`aget()` in a loop before opening the pipeline; tests that pass under quiescent conditions but have no concurrent-mutation case; TTL applied to a key that returns `EXISTS 0`.

**Phase to address:** Atomic-application-mechanism phase (the Lua-vs-Python decision). This is the phase-0 fork.

---

### Pitfall 2: Dynamically-discovered child keys are not in `KEYS[]` — breaks Redis Cluster and replication correctness

**What goes wrong:**
A server-side Lua traversal reads a parent, extracts a child key string from its JSON, and calls `redis.call('EXPIRE', child_key, ttl)` where `child_key` came from `JSON.GET`, not from `KEYS[]`. On Redis Cluster this hard-fails: *"Lua script attempted to access a non local key in a cluster node."* Even on standalone, accessing keys not declared in `KEYS[]` is officially unsupported and undermines the guarantees effect-replication/AOF rely on.

**Why it happens:**
Cascade fundamentally means "touch keys I discover at runtime," which is the exact anti-pattern Redis scripting forbids. Developers testing only on standalone `redis-stack-server` (as rapyer's whole suite does) never see the cluster failure.

**How to avoid:**
Decide and document the deployment boundary up front. For standalone: effect-based script replication (default since Redis 5.0, mandatory in 7.0) replicates the *resulting* `EXPIRE` commands, so a standalone master→replica setup stays correct even with dynamically-discovered keys — but write this down as the supported envelope. For Cluster support (future): the only correct patterns are (a) require all cascade-reachable keys to share a hash-tag/slot, or (b) two-phase — Python resolves keys, groups by slot, issues per-slot `EXPIRE` scripts with keys in `KEYS[]` (accepting non-atomicity across slots). Do not silently ship a cluster-incompatible script as "atomic cascade."

**Warning signs:**
`redis.call('EXPIRE', k, ...)` where `k` is a Lua local, not `KEYS[i]`; no cluster in the CI matrix; docs claiming atomicity without a "standalone only" caveat.

**Phase to address:** Atomic-application-mechanism phase; documented as a scope boundary in the config/scope phase.

**Verified:** [redis.io Lua API reference](https://redis.io/docs/latest/develop/programmability/lua-api/), [redis.io eval-intro](https://redis.io/docs/latest/develop/programmability/eval-intro/).

---

### Pitfall 3: Cyclic FK graphs cause infinite/exponential traversal without a visited-set AND depth guard

**What goes wrong:**
FK graphs contain cycles (A→B→A) and self-references (A→A, explicitly supported per ARCHITECTURE.md). A naive recursive cascade either loops forever (script never returns; Redis kills it at `busy-reply-threshold`/`lua-time-limit` and the connection is wedged) or, on a diamond graph (A→B, A→C, B→D, C→D), re-visits and re-`EXPIRE`s D exponentially.

**Why it happens:**
Depth-limiting alone is insufficient — a 2-node cycle with `max_depth=1000` still does 1000 pointless round trips. Visited-set alone is insufficient if the design allows re-entry via different paths before marking visited. Both guards are needed, and inside Lua the visited set must be a Lua table keyed by resolved key string, reset per invocation.

**How to avoid:**
Two independent guards, both configurable via `CascadeTTL`: (1) a `visited` set keyed by fully-resolved Redis key string, checked-and-inserted *before* recursing; (2) a hard `max_depth` decrement that stops traversal regardless. Make `max_depth` part of `CascadeTTL` config (PROJECT.md requires "configurable cycle-safe depth"). Default depth should be small (e.g. 1–3) so a misconfiguration degrades to shallow, not runaway.

**Warning signs:**
Lua `BUSY` errors / `SCRIPT KILL` needed; cascade latency scaling super-linearly with graph size; a cascade that touches the same key twice.

**Phase to address:** Traversal-and-cycle-safety phase. Requires explicit cyclic-graph and diamond-graph integration tests.

---

### Pitfall 4: Calling RedisJSON commands (`JSON.GET`) from inside Lua diverges between fakeredis and real Redis

**What goes wrong:**
The traversal must read each node's FK fields, which live in the RedisJSON document — meaning `redis.call('JSON.GET', key, path)` inside the cascade script. fakeredis implements Lua via `lupa` (Lua 5.1) and RedisJSON via `jsonpath-ng` — two independent reimplementations. Module-command dispatch *from within* a Lua script is a known weak seam: return shapes, path semantics, and `cjson.null`-vs-`nil` handling can differ from real RedisJSON, so unit tests (fakeredis) pass while integration (real Redis Stack) fails, or vice-versa. This is the exact class of bug already burned in 1.3.3 (`JSON.MGET` returning `[]` vs `None`).

**Why it happens:**
CONCERNS.md explicitly flags "New Lua-script-based features are the highest-risk category for fakeredis divergence, since fakeredis's Lua support is a reimplementation." Combining Lua + RedisJSON in one call stacks two reimplemented layers.

**How to avoid:**
Every cascade Lua script must have integration coverage against `real_redis_client`, not fakeredis alone (CONCERNS.md migration plan). Normalize the `JSON.GET` result explicitly in Lua: guard `cjson.null`, handle both "array-wrapped path result" and "scalar" shapes, and reuse the existing shared missing-key guard pattern (`aget`/`afind`) rather than a new per-script check. Prefer returning FK key strings from the script as a flat Lua array (not nested JSON) to minimize `cjson` surface. Consider whether cascade tests need to be marked integration-only if fakeredis can't f+faithfully model `JSON.GET`-in-Lua.

**Warning signs:**
Cascade tests green on `tests/unit/` (fakeredis) but red on `tests/integration/`; `IndexError`/`KeyError` on missing child keys; `cjson.null` leaking into Python as a truthy sentinel.

**Phase to address:** Traversal phase (script authoring) + a dedicated dual-backend testing phase/gate. Add cascade subclasses to the `ActionTestBase` framework so action-coverage enforces both backends.

**Verified:** [fakeredis docs](https://fakeredis.readthedocs.io/en/latest/redis-stack/), [fakeredis-py #304 Lua support](https://github.com/cunla/fakeredis-py/issues/304), [redis.io cjson notes](https://redis.io/docs/latest/develop/programmability/lua-api/).

---

### Pitfall 5: Cascade Lua script must register through `SCRIPT_REGISTRY` and the NOSCRIPT self-heal path — not a hand-rolled EVAL

**What goes wrong:**
A cascade implemented as a raw `EVAL` (or a script loaded outside `register_scripts`) will not be re-registered when Redis flushes its script cache (`SCRIPT FLUSH`, restart, failover). The first `EVALSHA` after a cache eviction throws `NoScriptError` and the cascade fails permanently instead of self-healing, because only scripts in `SCRIPT_REGISTRY` participate in `handle_noscript_error` re-registration.

**Why it happens:**
CONCERNS.md: "any new cascade Lua scripts added for cross-key cascade operations must be registered through `rapyer/scripts/registry.py` so they participate in this same recovery path, not hand-rolled `EVAL` calls." The registry is a simple list literal that's easy to forget to append to.

**How to avoid:**
Add the cascade script to `SCRIPT_REGISTRY` (`rapyer/scripts/registry.py:28`) with a constant name in `scripts/constants.py`, invoke it via `arun_sha`/`run_sha` (never `client.evalsha`/`client.eval` directly), and confirm it survives the existing `flush_scripts` test fixture. If the cascade needs SF save/load logic, use the `--[[SF_DISPATCH_TABLE]]` placeholder mechanism rather than duplicating snippets.

**Warning signs:**
`client.eval(` or `client.evalsha(` anywhere in cascade code; a cascade script name absent from `SCRIPT_REGISTRY`; no `flush_scripts`-fixture test for cascade.

**Phase to address:** Atomic-application-mechanism phase.

---

### Pitfall 6: Overwrite-vs-extend semantics on child TTL are undefined and will corrupt data either way if not decided

**What goes wrong:**
When a parent with TTL=3600 cascades to a child, what happens to the child's *existing* TTL? Four wrong defaults: (a) blindly `EXPIRE child 3600` shortens a child that had a longer independent TTL or resurrects a persistent (no-TTL) child into a mortal one; (b) `EXPIRE child ... GT` keeps only the max but silently ignores the cascade intent; (c) skipping children that already have a TTL breaks refresh-on-parent-read; (d) `PERSIST`-then-set races. A child shared by two parents (Pitfall 7) makes any single-writer assumption wrong.

**Why it happens:**
"Per-field TTL *values*" and "overwrite vs extend" are listed as TBD/uncommitted in PROJECT.md Out-of-Scope. Shipping cascade without deciding this defaults to "last writer wins," which is nondeterministic under concurrency.

**How to avoid:**
Make the policy an explicit, named field on `CascadeTTL` (e.g. `overwrite` | `extend_only` | `max`) with a documented default, and implement it with the atomic `EXPIRE ... GT`/`LT`/`NX`/`XX` flags (Redis 7.0+) *inside* the script so the compare-and-set is atomic. If targeting Redis 6.x (CI matrix runs redis 6.0–7.4), those `EXPIRE` flags don't exist on 6.x — must emulate via `PTTL` read + conditional `PEXPIRE` in the same script. Pin the semantics with tests per policy value.

**Warning signs:**
A child's TTL changing unexpectedly after an unrelated parent read; persistent children acquiring TTLs; `EXPIRE ... GT` used but CI includes redis 6.0.

**Phase to address:** Config-surface phase (name the policy) + traversal phase (implement atomically). Verify Redis-version support of `EXPIRE` flags against the 6.0–7.4 matrix.

---

### Pitfall 7: Children shared by multiple parents, dangling FK keys, and self-references break naive cascade

**What goes wrong:**
(a) **Shared child:** child C referenced by parents A and B. A's cascade sets C's TTL to A's value; B's later cascade overwrites it. Neither parent "owns" C, so C's lifetime is whichever parent touched it last — a data-loss surprise (C may expire while B still references it). (b) **Dangling FK:** `ForeignKey` is an unenforced string (CONCERNS.md: "a `ForeignKey` can be constructed from an arbitrary string key that doesn't exist"). Cascade hits `EXPIRE missing_key` (no-op, silently succeeds — like the `adelete_many` silent-skip) masking a broken graph. (c) **Self-reference:** A→A means the parent's own key appears as a "child" and gets its TTL set twice / competes with the root TTL write.

**Why it happens:**
FK is a lazy pointer with no referential integrity (ARCHITECTURE.md, CONCERNS.md "No table-like relational integrity constructs"). Cascade is the first feature to treat FKs as a graph, exposing all the integrity gaps at once.

**How to avoid:**
- Shared child: document that cascade TTL is "max-wins" or "last-writer" explicitly (ties to Pitfall 6); do not pretend ownership exists. Consider `EXPIRE ... GT` so a shared child keeps the longest requested lifetime.
- Dangling FK: decide whether a missing child is a silent skip (consistent with existing `adelete_many` behavior) or a surfaced warning — CONCERNS.md flags the silent-skip masking risk. Prefer counting/telemetry so partial cascades are observable.
- Self-reference: dedup via the visited-set (Pitfall 3) keyed by resolved key, and ensure the root key is written exactly once (the existing `_ttl_keys()` root+SF-keys logic already owns the root; cascade must not double-touch it).

**Warning signs:**
A child expiring while a live parent still points at it; cascade "succeeding" on a graph with broken references; the root key's TTL being set by both the base refresh and the cascade.

**Phase to address:** Traversal phase (visited-set + missing-key policy) + config phase (shared-child TTL policy).

---

### Pitfall 8: Backward-compatibility with `Meta.ttl` / `refresh_ttl` and the "refresh_ttl excludes DELETE" invariant

**What goes wrong:**
Cascade layers onto an existing, subtle TTL system: (a) `refresh_ttl` is validated to reject `ActionGroup.DELETE` (`config.py:70-80`, `_no_delete_in_refresh_ttl`) because a deleted key can't be refreshed. A cascade action group must respect the same rule or the validator throws / the invariant leaks. (b) `init_rapyer(ttl=...)` overwrites *every* model's `Meta.ttl` uniformly (CONCERNS.md) — a global cascade default set at init could clobber or be clobbered by this. (c) The V1/V2 `mark_actions` dual path (CONCERNS.md) means a cascade decorated with the wrong `MarkVersion` gets different refresh semantics. (d) TTL refresh must resolve to the *root* model (`resolve_root_model`); a cascade triggered through a nested model or SF that bypasses this refreshes the wrong key (the exact 1.3.3 bug).

**Why it happens:**
The action/TTL system is a large, fragile, multi-responsibility surface (`base.py` 1331 lines; CONCERNS.md "High blast radius"). Cascade is the biggest new consumer of it.

**How to avoid:**
- Route cascade through `register_action_target`/`resolve_root_model`, never touch `Meta.ttl`/`EXPIRE` directly (CONCERNS.md explicit instruction).
- Make cascade additive/opt-in: default `CascadeTTL` off, so existing single-aggregate `_ttl_keys()` behavior is byte-for-byte unchanged when no cascade is configured. `TwoModelDeleteBase` and existing TTL tests must still pass unmodified.
- Model the global cascade default so it composes with `init_rapyer(ttl=...)` predictably (decide precedence: per-field override > global cascade default > `Meta.ttl`).
- If cascade introduces a new `ActionGroup` bit, extend `_no_delete_in_refresh_ttl` reasoning consistently and add it as a narrowly-scoped new method/mixin, not by growing `__init_subclass__` (CONCERNS.md).

**Warning signs:**
Existing TTL/`refresh_ttl` tests changing behavior; `InvalidRefreshTtlError` firing unexpectedly; TTL landing on a nested/child key instead of the root; a cascade method defaulting to `MarkVersion.V1`.

**Phase to address:** Config-surface phase + integration phase. Regression-gate against the existing TTL and `TwoModelDeleteBase` suites first.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Python-side graph resolution + one `EXPIRE` pipeline | Simple, no new Lua, easy to test on fakeredis | Non-atomic (TOCTOU, Pitfall 1); contradicts the #1 project constraint | Only as a throwaway spike to validate the config surface — never as the shipped mechanism |
| Depth guard only, no visited-set | Easy to implement | Wasted round trips / re-`EXPIRE` on cycles & diamonds (Pitfall 3) | Never — both guards are cheap |
| Silent-skip on dangling/missing FK child | Matches existing `adelete_many` behavior; no new error type | Masks broken graphs and partial cascades (Pitfall 7b) | Acceptable as default IF paired with a count/telemetry surface distinguishing "absent" from "expired" |
| `EXPIRE child ttl` with no overwrite policy | One line | Corrupts shared/longer-lived/persistent children (Pitfall 6/7a) | Never — name the policy even if the default is "overwrite" |
| Test cascade on fakeredis only | Fast CI, no Redis service | `JSON.GET`-in-Lua divergence ships undetected (Pitfall 4) | Never for the Lua path — integration coverage is mandatory |
| New `EVAL` outside `SCRIPT_REGISTRY` | Fewer files to touch | No NOSCRIPT self-heal → hard failure after cache flush (Pitfall 5) | Never |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Redis Cluster | Assuming the "atomic server-side" script works in cluster | It fails with "non local key" for discovered keys; require same-slot hash-tags or two-phase per-slot, and document standalone-only if not solved |
| Redis replication/AOF | Assuming dynamically-discovered `EXPIRE`s replicate correctly | They do under effect-based replication (Redis 5.0+, mandatory 7.0) for standalone — the *effects* (EXPIRE commands) are replicated, not the script; still declare the standalone boundary |
| RedisJSON via Lua | Treating `JSON.GET` return as a Python-shaped value | It's a JSON string / `cjson`-decoded table with `cjson.null` (not `nil`) for JSON null; normalize explicitly |
| Redis 6.x in CI matrix | Using `EXPIRE ... GT/LT/NX/XX` for overwrite policy | Those flags are 7.0+; emulate via `PTTL`+conditional `PEXPIRE` in-script to support the 6.0–7.4 matrix |
| fakeredis (`lua`,`json`) | Trusting green unit tests as proof of Lua correctness | fakeredis Lua is `lupa`/`jsonpath-ng` reimplementation; gate the Lua path on `real_redis_client` |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Exponential re-visit on diamond graphs | Cascade latency super-linear in node count | Visited-set keyed by resolved key (Pitfall 3) | As soon as any node is reachable by >1 path |
| Deep cascade blocking the single-threaded Redis | Other clients stall; `BUSY` / `lua-time-limit` errors | Small default `max_depth`; keep script work bounded; consider fan-out cap | Deep or wide graphs; large SF keysets per node |
| N+1 inside the script (one `JSON.GET` per node serially) | High per-cascade latency | Batch reads where the shape allows; keep traversal breadth-first with grouped reads | Wide graphs (many children per parent) |
| Cascade re-touching every SF key of every node | Round trips = nodes × SF-keys-per-node | Reuse `_all_keys_for_key`/`_ttl_keys` recursion, don't re-enumerate | Nodes with many nested special fields |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Building cascade key strings from untrusted FK values without validation | An attacker-writable Redis or crafted FK string could point cascade `EXPIRE` at arbitrary keys | Treat Redis as a trusted store (existing CONCERNS.md posture); validate/namespace resolved keys against known model prefixes before `EXPIRE` |
| Growing the Lua/`eval` attack surface while bandit/semgrep/CodeQL stay non-blocking | New Lua paths merge without security gating (CONCERNS.md: scanners are `exit_zero`/`continue-on-error`) | Consider wiring bandit/semgrep results into required checks once cascade adds Lua paths |

## UX Pitfalls (developer-facing API)

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Cascade on by default | Existing users silently get cross-key TTL changes on upgrade | Opt-in; default `CascadeTTL` disabled; additive per PROJECT.md compatibility constraint |
| Unclear precedence between global default, per-field override, and `Meta.ttl` | Users can't predict a child's TTL | Document a single precedence rule (per-field > global cascade > `Meta.ttl`) and test it |
| Cascade config on the FK field but semantics (overwrite/extend/depth) hidden | Users misconfigure and get data loss | Make every semantic an explicit named `CascadeTTL` field with documented defaults |
| Silent partial cascade on broken graphs | Users think TTL propagated when it didn't | Return/telemetry a count of keys touched vs skipped |

## "Looks Done But Isn't" Checklist

- [ ] **Cascade traversal:** Often missing the cyclic + diamond + self-reference cases — verify with dedicated graph-shape integration tests, not just linear parent→child.
- [ ] **Atomicity:** Often "atomic" only under quiescence — verify with a concurrent-mutation test (delete/relink a child mid-cascade) and confirm the Lua path (not Python resolution) is used.
- [ ] **Lua script lifecycle:** Often missing NOSCRIPT recovery — verify the cascade script is in `SCRIPT_REGISTRY` and survives the `flush_scripts` fixture.
- [ ] **Dual-backend tests:** Often green on fakeredis only — verify the cascade Lua/`JSON.GET` path runs and passes against `real_redis_client`.
- [ ] **Overwrite policy:** Often "just `EXPIRE`" — verify shared-child, longer-lived-child, and persistent-child cases behave per the documented policy.
- [ ] **Backward-compat:** Often untested against existing behavior — verify existing TTL, `refresh_ttl`, and `TwoModelDeleteBase` suites pass unchanged with cascade disabled.
- [ ] **Redis-version support:** Often assumes 7.0 `EXPIRE` flags — verify against redis 6.0 in the CI matrix.
- [ ] **Root resolution:** Often refreshes the wrong key from a nested trigger — verify cascade goes through `resolve_root_model`.
- [ ] **Cluster boundary:** Often undocumented — verify docs state standalone-only (or cluster strategy) explicitly.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Shipped non-atomic Python traversal (P1) | HIGH | Rewrite as registered Lua script; may require re-designing config API if it assumed Python resolution |
| Cluster incompatibility discovered late (P2) | HIGH | Add hash-tag requirement or two-phase per-slot mode; document standalone-only as interim |
| Infinite/exponential traversal in prod (P3) | MEDIUM | `SCRIPT KILL`; add visited-set + depth guard; lower default depth via config hotfix |
| fakeredis-only tests hid a real-Redis bug (P4) | MEDIUM | Add `real_redis_client` cascade coverage; fix `JSON.GET`/`cjson.null` normalization |
| Missing NOSCRIPT registration (P5) | LOW | Append to `SCRIPT_REGISTRY`, route via `arun_sha`, add `flush_scripts` test |
| Undefined overwrite policy corrupting TTLs (P6/P7) | MEDIUM | Introduce named policy field (default preserves current behavior); use atomic `EXPIRE` flags / in-script compare-set; backfill via re-save |
| Broke existing `refresh_ttl`/`Meta.ttl` behavior (P8) | MEDIUM | Make cascade opt-in/default-off; restore existing suites as regression gate |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| P1 Atomicity / TOCTOU | Atomic-application-mechanism (phase 0 fork) | Concurrent-mutation integration test; assert single `EVALSHA`, no pre-pipeline `afetch` loop |
| P2 KEYS[]/cluster/replication | Atomic-application-mechanism + config scope-boundary | Documented standalone envelope; (future) cluster CI job |
| P3 Cycles / exponential traversal | Traversal-and-cycle-safety | Cyclic, self-ref, and diamond graph tests; latency bounded |
| P4 fakeredis vs real Redis divergence | Traversal (script authoring) + dual-backend test gate | Cascade `ActionTestBase` subclass passing on `real_redis_client` |
| P5 NOSCRIPT / registry | Atomic-application-mechanism | Script in `SCRIPT_REGISTRY`; passes `flush_scripts` fixture |
| P6 Overwrite-vs-extend semantics | Config-surface + traversal | Per-policy tests; Redis 6.0–7.4 matrix for `EXPIRE` flags |
| P7 Shared/dangling/self-ref children | Traversal + config-surface | Shared-child, missing-child, self-ref tests; telemetry on skips |
| P8 Backward-compat with `refresh_ttl`/`Meta.ttl` | Config-surface + integration | Existing TTL + `TwoModelDeleteBase` suites pass unchanged with cascade off |

## Sources

- [Redis Lua API reference — keys must be in KEYS[], cjson, replication](https://redis.io/docs/latest/develop/programmability/lua-api/) (HIGH)
- [Redis Scripting with Lua (eval-intro) — effect replication, non-determinism, key-expiry frozen during script](https://redis.io/docs/latest/develop/programmability/eval-intro/) (HIGH)
- [Redis replication docs](https://redis.io/docs/latest/operate/oss_and_stack/management/replication/) (HIGH)
- [redis/redis #5208 — forbid non-deterministic write commands](https://github.com/redis/redis/pull/5208) (MEDIUM)
- [antirez — Recent improvements to Redis Lua scripting (effects replication)](https://antirez.com/news/97) (MEDIUM)
- [fakeredis redis-stack support docs](https://fakeredis.readthedocs.io/en/latest/redis-stack/) (HIGH)
- [fakeredis-py #304 — better Lua support](https://github.com/cunla/fakeredis-py/issues/304) (MEDIUM)
- Codebase: `rapyer/base.py` (`refresh_ttl`, `aset_ttl`, `_ttl_keys`, `_all_keys_for_key`), `rapyer/config.py` (`refresh_ttl` validator, `ttl`, `max_delete_per_transaction`), `rapyer/scripts/registry.py` (`SCRIPT_REGISTRY`, `arun_sha`, NOSCRIPT self-heal), `.planning/codebase/CONCERNS.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/TESTING.md`, `CHANGELOG.md`, `.planning/PROJECT.md` (HIGH)

---
*Pitfalls research for: TTL cascade over Redis across ForeignKey relationships (rapyer)*
*Researched: 2026-07-06*
