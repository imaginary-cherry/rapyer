# Project Research Summary

**Project:** rapyer — Configurable TTL Cascade
**Domain:** Atomic, set-time TTL propagation across a RedisJSON ForeignKey graph in an async Python ORM (`rapyer`)
**Researched:** 2026-07-06
**Confidence:** HIGH (stack/features/pitfalls verified against official Redis + ORM docs and read directly from rapyer source; one MEDIUM area: fakeredis JSON-in-Lua parity)

## Executive Summary

This milestone adds the first slice of a **configurable cascade framework**: TTL that propagates from a parent aggregate to its `ForeignKey`-referenced children, applied **atomically, server-side, at set-time**. It is an additive slice on a mature brownfield codebase. Every primitive it needs already exists — `redis.asyncio` (`EVALSHA`, `EXPIRE`/`PEXPIREAT`, transactional pipelines), the `SCRIPT_REGISTRY` + NOSCRIPT self-heal machinery, RedisJSON, and pydantic v2 for the config object. **No new third-party dependency is required.** The engineering is not in the tooling; it is in *where the FK-graph walk lives* and *how the apply stays atomic without breaking Redis Cluster, replication, or the fakeredis unit tier*.

The four research tracks converged on the config surface and the pitfalls but **disagreed on the central open decision — the traversal-resolution approach.** STACK leans **Option A** (full recursive server-side Lua traversal via a class→FK-JSONPath dispatch table injected like the existing SF-dispatch). ARCHITECTURE recommends **Option B** (Python-side FK-graph traversal building a flat key list, then a single registered `cascade_ttl_apply` Lua that `PEXPIREAT`s the whole list). PITFALLS frames the "Governing Tension" — cascade child keys are discovered by following FK pointers *inside* the parent JSON, so they cannot be pre-declared in `KEYS[]`, producing a trilemma among *atomic+server-side*, *Cluster/replication-correct*, and *simple*. **This SUMMARY resolves that decision in favor of Option B** (rationale below), because the milestone's real atomicity requirement is about the *propagation* (the EXPIRE fan-out), and for idempotent TTL the discovery TOCTOU window is provably benign.

The dominant risks are all downstream of that structural fact: dynamically-discovered keys break Cluster and undermine replication guarantees; cyclic/diamond/self-referential FK graphs need both a visited-set and a depth guard; `JSON.GET`-from-Lua is the codebase's single highest fakeredis-divergence area; and the `mode`-to-`EXPIRE`-flag mapping (GT/NX/XX) only exists on Redis 7.0+ while CI runs a 6.0–7.4 matrix. All are mitigated by choosing B, keeping cascade opt-in and disabled-by-default, routing every touch through `resolve_root_model` + `SCRIPT_REGISTRY`, and gating the Lua path on a real-Redis integration suite.

## Key Findings

### Recommended Stack

Conservative and reuse-first: compose existing Redis/Lua/redis-py primitives rather than introduce new runtime machinery (see `STACK.md`). The cascade apply slots into the existing template → variant-substitution → `SCRIPT_LOAD` → cached-SHA → `EVALSHA` (with `NoScriptError` self-heal) pipeline. Stay inside the current pins; do **not** bump to redis-py 8.x (RESP3-default would silently break the `JSON.GET` array-unwrap the codebase relies on), and do **not** adopt Redis Functions/`FCALL` (needs Redis 7.0+, unsupported by fakeredis, forks the whole scripts layer for no user-visible gain this milestone).

**Core technologies (all already in the lockfile — no new deps):**
- `redis-py` (`redis.asyncio`) `>=6.0.0,<7.5.0` (locked 7.0.1): `evalsha`, `pipeline.evalsha`, `expire`/`pexpire`, transactional pipeline — every cascade primitive present since redis-py 4.x/5.x, no version bump.
- Redis Stack (RedisJSON) 6.0–7.4 matrix: `JSON.GET`/`JSON.MGET` to read FK key-strings, `PEXPIREAT` (absolute, deterministic under effects replication) for the apply.
- Existing `rapyer.scripts` machinery: register `cascade_ttl_apply` in `SCRIPT_REGISTRY` so it inherits NOSCRIPT recovery; invoke only via `arun_sha`/`run_sha`.
- `pydantic` v2 (locked 2.12.5): model the `CascadeTTL` config object as a pydantic model attached via `Annotated`, mirroring `Key[...]`/`Index[...]`.

### Expected Features

Prior art (SQLAlchemy, Django, Prisma, redis-om, Beanie) is consistent: cascade behavior is **a small set of named, symbolic options declared per relationship, with a sensible default** — never a raw boolean or a free-form callback (see `FEATURES.md`).

**Must have (table stakes):**
- Named `CascadeTTL` config object (not `cascade=True`) — discoverable, IDE-completable, extensible backbone.
- Per-field opt-out (`enabled`) — required so a shared child can be excluded from a short-lived referrer.
- Global default + per-field `Annotated` override — the stated config model; global default ships **disabled**.
- Cycle-safe traversal with a max-depth guard — non-negotiable given self-references already ship.
- Atomic set-time propagation — the Core Value; no partial/interleaved apply.
- Backward-compatible coexistence with `Meta.ttl` / `refresh_ttl` — byte-for-byte unchanged when cascade is off.

**Should have (competitive differentiators):**
- **TTL cascade across references at all** — the headline; **no Redis ORM does this** (redis-om has only flat per-model `default_ttl`).
- Extend-vs-overwrite `mode` mapped to native Redis `EXPIRE` flags — atomic, zero extra round trips, kills the "short-lived referrer shortens a shared child" footgun. `EXTEND` (GT) is the defensible default.
- Configurable traversal `depth` as a first-class knob (0 = root only, 1 = direct children, N hops).

**Defer (v1.x / v2+):**
- `IF_UNSET` (NX) and `LT`/`SHORTEN` modes — add after base semantics prove out (enum stays additive).
- Delete cascade and save cascade — future rules on the *same* backbone (design the seam now, implement only TTL).
- Reverse/inbound cascade — gated on a reference/reverse index that does not exist.
- Per-child distinct TTL *values* — ambiguous multi-parent semantics; only if a concrete use case emerges.

### Recommended `CascadeTTL` Config Schema

Disabled-by-default, global default + per-field override, `mode` enum mapping 1:1 to Redis 7 `EXPIRE` conditional flags:

```python
class TTLCascadeMode(enum.Enum):
    OVERWRITE = "overwrite"  # plain EXPIRE — parent lifecycle strictly governs children
    EXTEND    = "extend"     # EXPIRE ... GT — only lengthen a child's TTL, never shorten (DEFAULT)
    IF_UNSET  = "if_unset"   # EXPIRE ... NX — only stamp children that currently have no TTL

class CascadeTTL(BaseModel):
    enabled: bool = True                      # per-field opt-out (global default ships enabled=False)
    depth: int = 1                            # 0 = root only, 1 = direct children, N = N hops (cycle-guarded)
    mode: TTLCascadeMode = TTLCascadeMode.EXTEND
    # direction fixed forward (parent -> referenced child) in v1; not a knob yet
```

- **Global default**: a single `CascadeTTL` set at `init_rapyer(..., cascade_ttl=...)`, assigned onto models the way `Meta.ttl` is wired. Ships as `CascadeTTL(enabled=False)` so existing projects are unchanged until opt-in.
- **Per-field override**: `Annotated[Reference[Author], CascadeTTL(mode=..., depth=...)]`, reusing the established annotation-marker machinery. **Precedence: per-field override > global cascade default > `Meta.ttl`** (document and test this single rule).
- **`EXTEND` (GT) default**: matches rapyer's push-expiry-out refresh philosophy; GT treats a non-volatile key as infinite TTL, so it **never** starts expiring an intentionally-persistent shared child.

### Architecture Approach

Cascade lands as a new, narrowly-scoped `rapyer/cascade/` subpackage — **not** by growing the already-1331-line `AtomicRedisModel` — with the graph walk (`planner`) deliberately decoupled from the leaf action (`apply`) so future delete/save cascade reuse the traversal and swap only the apply. `base.py` gains a thin detection branch and a `_cascade_ttl_keys()` expansion; the action boundary (`resolve_root_model` / `register_action_target` / `ensure_pipeline`) stays the single place TTL is resolved (see `ARCHITECTURE.md`).

**Major components:**
1. `CascadeSpec` / `CascadeTTL` (`rapyer/cascade/config.py`) — value object + global-default state; per-field via `Annotated`.
2. `CascadePlanner` (`rapyer/cascade/planner.py`) — operation-agnostic, cycle-safe, depth-guarded graph walk emitting a flat, de-duplicated key list; reuses `_relational_target`, `target_key`, `_all_keys_for_key` (no fetch of leaf children).
3. Apply strategies (`rapyer/cascade/apply.py`) + `cascade_ttl_apply.lua` — a single registered `PEXPIREAT`(-with-mode) fan-out over the key list, riding the triggering write's MULTI/EXEC.
4. Action-boundary integration — `refresh_ttl`/`aset_ttl` expand to `_cascade_ttl_keys()` only when the root has cascade-enabled FKs; the no-config path is untouched.

### Reconciled Traversal Approach — RECOMMEND OPTION B

**Decision: Option B — Python-side FK-graph traversal → flat key list → one registered `cascade_ttl_apply` Lua (`PEXPIREAT`/mode-flag over the list).**

The trilemma dissolves for TTL specifically because the milestone's atomicity constraint is about the **propagation (the EXPIRE fan-out), not the discovery**. That fan-out *is* one atomic server-side script in B. The only window is between reading the child set and expiring it, and for idempotent TTL that window is **benign**: a child deleted/re-pointed in it → `PEXPIREAT` on a missing key is a harmless no-op; a child added in it → not covered by this cascade, but covered by *its own* set-time cascade (the trigger is set-time by design). No half-expired graph, no orphaned inconsistency.

Given that, B wins on the factors that hit A hardest:
- **The SF-dispatch precedent does not generalize.** SF dispatch keys on a *closed, finite set of SF types*; cascade metadata keys on an *unbounded, open set of user model classes* with per-field FK topology — a second, parallel source of truth that silently mis-expires on any drift. B reads live Python metadata at traversal time (no duplication).
- **Redis Cluster:** A hard-fails (`CROSSSLOT` / "non-local key") on discovered cross-slot keys with **no in-script fallback**; B degrades gracefully (per-slot atomic batches or a documented non-atomic fan-out).
- **fakeredis divergence** (the codebase's single highest-risk category per CONCERNS.md): A stacks recursive Lua + `JSON.GET` + `cjson` — exactly the weak seam; B's discovery is pure Python and its apply is a trivial `PEXPIREAT` loop.
- **Extensibility:** B's planner extends cleanly to future delete/save cascade (swap the apply); doing irreversible cross-key deletes inside recursive Lua has no rollback.
- **Debuggability + testability:** cycle/depth logic in ordinary, unit-testable Python.

**The risk that would flip the decision to A:** if the atomicity requirement is (re)interpreted to require that *discovery itself* be atomic — i.e., a child added/relinked mid-traversal MUST be covered by the same cascade — then only server-side traversal satisfies it, and B is insufficient. This becomes real the moment a **non-idempotent** op (delete cascade) is in scope, because the benign-TOCTOU argument is TTL-specific. For this TTL-only milestone it does not apply; the backbone must re-examine the window when delete cascade lands. Note A cannot satisfy this on Cluster anyway, so "strict discovery atomicity" is only ever a standalone-only guarantee.

**A phase-level spike MUST confirm, before locking the apply script:**
1. **fakeredis JSON-in-Lua / apply parity** — even B's apply must be validated against `real_redis_client`, and any `JSON.GET`-in-Lua (if the apply reads JSON at all) treated as the highest-risk seam; budget a `loader.py` variant branch or mark cascade Lua integration-only if fakeredis can't model it.
2. **`mode`-flag Redis-version support** — `EXPIRE ... GT/NX/XX` are **Redis 7.0+ only**, but CI runs the **6.0–7.4** matrix. The spike must decide: either emulate the mode via `PTTL` read + conditional `PEXPIRE(AT)` *inside the same script* (keeps 6.x), or raise the documented minimum server version to 7.0. Do not ship GT/NX against a 6.0 rung untested.

### Critical Pitfalls (top of `PITFALLS.md`, all downstream of the "keys aren't in KEYS[]" tension)

1. **Multi-round-trip Python traversal "looks atomic" but isn't** — for delete/save it would break; for **TTL it is acceptable** *only because* EXPIRE-on-missing is a no-op and new nodes self-cover. State this as the explicit, reasoned envelope (B), not a hidden shortcut. Avoid any pre-pipeline `afetch()` loop masquerading as atomic.
2. **Dynamically-discovered keys break Cluster + replication correctness** — document a **standalone-only** supported envelope this milestone (effects replication carries the resulting `EXPIRE`s correctly for master→replica); B degrades on Cluster, A cannot.
3. **Cyclic / diamond / self-referential graphs** — require **both** a `visited` set (keyed by resolved key string) **and** a hard `depth` decrement; depth alone still burns round trips on a 2-node cycle. Default depth small (1–3). Test cyclic, self-ref, and diamond shapes explicitly.
4. **`JSON.GET`-from-Lua fakeredis divergence** — the exact 1.3.3 bug class (`[]` vs `None`); every cascade Lua path needs `real_redis_client` integration coverage and explicit `cjson.null`/array-shape normalization. Never trust green fakeredis alone.
5. **Cascade Lua must register through `SCRIPT_REGISTRY` + NOSCRIPT self-heal** — a hand-rolled `EVAL`/`evalsha` fails permanently after `SCRIPT FLUSH`/restart/failover; add the constant + registry entry and confirm it survives the `flush_scripts` fixture.
6. **Overwrite-vs-extend policy must be named and atomic** — undefined default corrupts shared/persistent/longer-lived children; implement via the `mode` enum + atomic `EXPIRE` flags (with the 6.x emulation caveat above).
7. **Shared / dangling / self-referential children** — `EXTEND` (GT) for shared children; decide missing-child = silent-skip-with-telemetry; dedup the root via the visited set so cascade never double-touches the key `_ttl_keys()` already owns.
8. **Backward-compat with `refresh_ttl`/`Meta.ttl`** — route through `resolve_root_model`; ship default-off; keep existing TTL and `TwoModelDeleteBase` suites passing unchanged; respect the `refresh_ttl`-excludes-DELETE invariant if a new `ActionGroup` bit is added.

## Implications for Roadmap

Research (especially `ARCHITECTURE.md`'s dependency-ordered build order and the `PITFALLS.md` phase mapping) points to a clean layered sequence. Each phase gates on the prior; the risky logic (traversal) and the risky backend (Lua/fakeredis) are isolated so they can be tested hardest.

### Phase 1: Config + detection backbone (no behavior)
**Rationale:** Blocks everything; lowest risk; establishes the extensible seam.
**Delivers:** `CascadeSpec`/`CascadeTTL` (`enabled`/`depth`/`mode`), `TTLCascadeMode` enum, global-default state + `init_rapyer` wiring, `Annotated` marker, an *additive* `__init_subclass__` branch populating `_cascade_ttl_fields`.
**Addresses:** named config object, global default + per-field override, disabled-by-default, backward-compat.
**Avoids:** P8 (do not reorder the fragile `__init_subclass__` `safe_issubclass` checks; establish precedence rule per-field > global > `Meta.ttl`).

### Phase 2: Python traversal planner (cycle + depth safe)
**Rationale:** The riskiest *logic*; must be nailed before any apply exists. Depends on Phase 1.
**Delivers:** `CascadePlanner.traverse()` — per-level `JSON.MGET`, `visited` set + per-edge depth guard, reuse of `_relational_target`/`_all_keys_for_key`, emits a de-duplicated flat key list. No apply yet.
**Addresses:** cycle-safe configurable-depth traversal; the "which keys" half of atomic propagation.
**Avoids:** P3 (both guards), P7 (shared/dangling/self-ref + missing-child policy). Heavy unit + integration tests: cycles, self-refs, diamonds, depth caps, missing children.

### Phase 3: Atomic apply (spike, then implement)
**Rationale:** Isolates the highest fakeredis-divergence + Redis-version risk into one small script. Depends on Phase 2.
**Delivers:** the confirmatory spike (fakeredis parity; `mode`-flag 6.x emulation vs min-version decision), then `cascade_ttl_apply.lua` (`PEXPIREAT` absolute + mode), `scripts/constants.py` + `SCRIPT_REGISTRY` entry, `apply.py` TTL strategy invoked via `run_sha`.
**Uses (STACK):** existing `SCRIPT_REGISTRY`/NOSCRIPT machinery, `PEXPIREAT`, `EXPIRE` mode flags.
**Implements (ARCHITECTURE):** the apply component; confirms Option B.
**Avoids:** P4 (real-Redis coverage from day one), P5 (registry + `flush_scripts`), P6 (named policy + version-safe flags), P2 (documented standalone envelope).

### Phase 4: Action-boundary wiring + backward-compat regression
**Rationale:** Connects planner+apply to the real write path atomically. Depends on Phase 3.
**Delivers:** `_cascade_ttl_keys()`; expand `refresh_ttl`/`aset_ttl` only when cascade-enabled; join the triggering write's `ensure_pipeline` MULTI/EXEC.
**Avoids:** P1 (cascade rides the write's transaction, no leaked `afetch` loop), P8 (no-config path byte-for-byte unchanged; `TwoModelDeleteBase` + existing TTL suites pass unmodified — run these as the regression gate *first*).

### Phase 5: Cascade integration test suite + docs/backbone stubs
**Rationale:** Closes the High-priority CONCERNS.md gap (no cross-model cascade tests) and proves the extensibility seam. Depends on Phase 4.
**Delivers:** `tests/integration/foreign_keys/` (multi-level, cyclic, mixed-SF-child, shared-child, cluster-note, concurrent-mutation) against `real_redis_client`; cascade docs page; documented, unimplemented `CascadeDelete`/`CascadeSave` extension points.
**Avoids:** re-tests P2/P3/P4/P7 end-to-end; documents the Cluster boundary explicitly.

### Phase Ordering Rationale
- **Config → planner → apply → wiring** follows the hard dependency chain and isolates each risk class (fragile `__init_subclass__`; traversal logic; Lua/fakeredis/version; the fragile TTL/action surface) into a phase that can be tested against the pitfall that threatens it.
- Traversal (Phase 2) precedes apply (Phase 3) so the "which keys" logic is proven in pure, debuggable Python before anything server-side runs — the core justification for choosing Option B.
- The Option-B decision means the apply is a *trivial* script, so the highest-risk fakeredis/version work is small and front-loaded via a spike inside Phase 3.

### Research Flags
Phases likely needing `/gsd:plan-phase --research-phase`:
- **Phase 3 (Atomic apply):** MEDIUM-confidence area — fakeredis `JSON.GET`/Lua parity and the `EXPIRE`-flag-vs-6.0 matrix decision are unresolved and must be settled by a spike before the script is locked.

Phases with well-documented / established patterns (skip deeper research):
- **Phase 1 (config):** mirrors existing `Key`/`Index`/`Meta.ttl` patterns.
- **Phase 2 (planner):** ordinary Python graph traversal over existing rapyer primitives.
- **Phase 4 (wiring):** reuses the documented `resolve_root_model` / `ensure_pipeline` boundary.
- **Phase 5 (tests/docs):** established `ActionTestBase` + dual-backend conventions.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | redis-py APIs, Lua sandbox rules, RedisJSON-from-Lua, cluster cross-slot verified against official docs and rapyer source; no new deps. MEDIUM only on fakeredis JSON-in-Lua parity. |
| Features | HIGH | Config shape corroborated across SQLAlchemy 2.0, Django, Prisma, redis-om, Beanie; `EXPIRE` NX/XX/GT/LT and redis-py signature verified against official docs. |
| Architecture | HIGH | All rapyer claims read directly from source; Cluster/replication/fakeredis claims are established Redis semantics + CONCERNS.md. Central A-vs-B decision is a judgment reconciled here, not a fact. |
| Pitfalls | HIGH | Cluster/replication/Lua-determinism verified against redis.io + Redis source discussions; codebase claims verified against `base.py`, `config.py`, `registry.py`, CONCERNS.md, CHANGELOG. |

**Overall confidence:** HIGH (with two scoped MEDIUM gaps below).

### Gaps to Address
- **fakeredis JSON-in-Lua / apply parity (MEDIUM):** resolve in the Phase 3 spike; be ready to add a `loader.py` variant branch or mark the cascade Lua path integration-only. Do not treat green fakeredis as proof.
- **`mode` flags vs Redis 6.0–7.4 CI matrix (MEDIUM):** `EXPIRE GT/NX/XX` are 7.0+. Phase 3 spike must choose `PTTL`+conditional-`PEXPIRE` emulation (keeps 6.x) or a documented 7.0 minimum. Blocks locking the apply semantics.
- **`_relational_target` name-based resolution fragility (issue #247):** the planner inherits this pre-existing risk; flag it in Phase 2, do not attempt to fix it here.
- **Cluster support:** explicitly out of envelope this milestone; document standalone-only. B leaves a graceful per-slot path open for the future; A would have hard-coded an anti-cluster ceiling.
- **Non-idempotent future ops:** the benign-TOCTOU argument that justifies Option B is TTL-specific; the delete/save-cascade phases must re-examine the discovery window before reusing the planner's apply.

## Sources

### Primary (HIGH confidence)
- redis.io Lua API reference & eval-intro — sandbox rules (keys must be in `KEYS[]`, no globals, no `require`), `cjson`, effects-only replication since 7.0, `allow-cross-slot-keys`/`no-cluster` flags, key-expiry frozen during script execution.
- redis.io `EXPIRE` / RedisJSON `JSON.GET`/`JSON.MGET` docs — NX/XX/GT/LT flags (7.0+), non-volatile-key-as-infinite GT semantics; `$`-path array-wrapping of `JSON.GET`.
- redis-py docs (`register_script`/NOSCRIPT, `evalsha`, `expire(nx/xx/gt/lt)`), Redis Cluster CROSSSLOT best-practices.
- ORM cascade docs: SQLAlchemy 2.0 cascades, Django `on_delete`, Prisma referential actions, redis-om `Meta.default_ttl`, Beanie `Link`/`WriteRules`/`DeleteRules`.
- rapyer source (read directly): `base.py` (`_all_keys_for_key`, `_iter_special_fields`, `_ttl_keys`, `refresh_ttl`, `aset_ttl`, `__init_subclass__`), `actions.py` (`resolve_root_model`, `register_action_target`), `context.py` (`ensure_pipeline`), `scripts/registry.py` (`SCRIPT_REGISTRY`, `_inject_sf_dispatch`, `arun_sha`), `scripts/loader.py`, `scripts/lua/atomic/get_or_create.lua`, `types/foreign_key.py`, `types/relational.py`, `config.py`; `.planning/codebase/CONCERNS.md`, `ARCHITECTURE.md`, `TESTING.md`, `CHANGELOG.md`, `.planning/PROJECT.md`.

### Secondary (MEDIUM confidence)
- fakeredis redis-stack docs + fakeredis-py #304 — Lua via `lupa` (5.1) + RedisJSON via `jsonpath-ng` as separate reimplementations; `JSON.GET`-in-Lua the divergence seam; `FUNCTION`/`FCALL` unsupported.
- redis/redis #5208, antirez effects-replication notes — non-deterministic-write history and why `EXPIRE`/`PEXPIREAT` are safe in-script under effects replication.

### Tertiary (LOW confidence)
- redis-py 8.0 RESP3-default behavioral edges — informs the "do not bump past `<7.5.0`" guard; exact 8.0 edge behavior not exercised here.

---
*Research completed: 2026-07-06*
*Ready for roadmap: yes*
