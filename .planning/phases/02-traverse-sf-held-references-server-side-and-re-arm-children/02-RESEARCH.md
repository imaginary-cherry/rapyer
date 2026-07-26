# Phase 2: Traverse SF-held references server-side and re-arm children - Research

**Researched:** 2026-07-25
**Domain:** Redis Functions library (Lua) traversal extension for a Python/pydantic-v2 Redis ORM (`rapyer`)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Test strategy — fakeredis reach coverage (D-01)
- **D-01:** **Status-quo fallback — do NOT add a Python-side traversal fallback.** The cascade Function stays the single source of traversal truth and is real-Redis-7+-only; fakeredis remains root-own-`EXPIRE`. Proving CASF-09 therefore splits by backend:
  - **Real Redis Stack :6370 (integration):** proves the actual SF reach — SET/ZSET members followed, each reached child re-armed to its own `Meta.ttl`, atomically, across the hard graph shapes below.
  - **fakeredis (unit):** proves the *fallback* — root-own keys refresh, cascade-enabled SF models init and run without crashing, children are (correctly) not re-armed on the fallback path; classification itself is already covered by Phase 1's static `build_cascade_plan` unit tests.
- **D-01a:** Rejected a Python-side fallback traversal that would duplicate the cycle/best-budget/depth logic in Python for hermetic unit coverage — two implementations to keep in sync is a divergence risk and exceeds the milestone's "traversal-reach only, apply unchanged, honor the documented fakeredis/real-Redis divergence" framing.

### Dangling / missing SF members (D-02)
- **D-02:** **Reuse the existing dangling handling — no new logic.** SF members flow through the same `push_child` → write-phase `EXPIRE` loop (`library.lua:323-345`); a member key whose target no longer exists makes `EXPIRE` a cheap no-op and is already tallied in `dangling_children_count`. No separate SF-dangling counter and no change to the `CascadeResult` return shape.

### Divergence observability (D-03)
- **D-03:** **Silent no-op on fakeredis** — no new logging/warning. This matches how inline cascade *already* behaves on fakeredis (the Function is simply not loaded), so SF-held-ref cascade stays consistent with the existing feature rather than singling itself out. The divergence is made visible through documentation (D-04 / CASF-10), not runtime noise.

### Documentation depth — CASF-10 (D-04)
- **D-04:** **Full docs, not the bare minimum.** Extend the cascade coverage matrix with the two new shapes (`RedisSet[ForeignKey[T]]`, `RedisPriorityQueue[ForeignKey[T]]`), update the relevant docstrings, AND add (a) a short worked RedisSet/PriorityQueue cascade example and (b) an explicit note that SF-held-ref cascade — like all cascade traversal — runs on real Redis 7+ and falls back to root-own-`EXPIRE` on fakeredis. Mirrors the existing v1.3.5 cascade docs style.

### Claude's Discretion
- Exact Lua structure for interleaving the SF read into the BFS: whether SMEMBERS/ZRANGE are issued inline in the `push_edges` per-node walk or in a small dedicated branch keyed on `edge.sf_container`, as long as members reach the same `push_child`/`next_hop`/`visited` machinery and the single-`JSON.GET` batch for inline refs is preserved for non-SF edges.
- Member decoding details (assuming `SMEMBERS`/`ZRANGE` return the plain target-key strings that `ForeignKey` serializes) — confirm during implementation and adjust if a decode/`byte`-vs-`str` shape surfaces on either backend.
- Precise selection and naming of the integration test graph fixtures on :6370, provided they cover the shapes enumerated under D-01 / Success Criteria.
- ZSET read form (`ZRANGE key 0 -1` vs equivalent) and any large-container concerns.

### Deferred Ideas (OUT OF SCOPE)
- **Python-side fallback traversal for fakeredis** (rejected as D-01a) — revisit only if hermetic unit coverage of the reach logic becomes a hard requirement and the divergence risk is judged acceptable.
- **Separate SF-dangling counter / distinct SF-hop error subtype** — deferred (D-02; Phase 1 D-04a) unless real usage shows the generic count/message is confusing.
- **SF containers holding nested inline submodels** (vs direct `ForeignKey[T]` elements) — out of milestone scope (REQUIREMENTS "Future").
- **Save/update/delete cascade apply through SF-held refs** — explicitly out of this milestone (traversal-reach only; the `CascadeSave`/`CascadeDelete` seams).
- Prior v1.3.5 robustness advisories retained: cascade-function self-heal (#284), WR-02/WR-03 (test freeze-leak / init freeze not exception-safe).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CASF-04 | Server-side traversal reads each cascade-enabled `RedisSet` key's members and follows every `ForeignKey` reference found there | Architecture Patterns / Pattern 1 gives the exact `edge.sf_container == 'set'` → `SMEMBERS` branch; Common Pitfall 1 covers the required `cjson.decode` unwrap verified live against real Redis |
| CASF-05 | Likewise for `RedisPriorityQueue`: reads sorted-set members and follows every `ForeignKey` reference found there | Same Pattern 1 branch, `edge.sf_container == 'zset'` → `ZRANGE key 0 -1`; empirically confirmed PQ members are ALSO JSON-quoted (not just SET members) |
| CASF-06 | Each child reached via an SF-held reference is re-armed to its own `Meta.ttl`, atomically, same operation as inline-reached children | `push_child`/write-phase EXPIRE loop reused verbatim (Don't Hand-Roll table); no plan-table or write-phase change needed since Phase 1 put SF edges in the same `entry.fks` list |
| CASF-07 | Cycle-safe + depth-budget traversal through SF containers, including diamonds, inline+SF shared children, self-references in a set/PQ | `visited`/`budget_is_larger`/`next_hop` reused unchanged (Don't Hand-Roll); Open Question 1 flags that dedicated hard-shape test fixtures (self-ref-in-SF, shared inline+SF child) don't yet exist and must be added by the plan |
| CASF-08 | Byte-for-byte preservation of existing inline behavior; additive/opt-in | Anti-Patterns section explains why the non-SF `JSON.GET` batch path must stay untouched (filter SF edges out of `paths`, not mixed in); existing regression suites (`test_cascade_graph_shapes.py` etc.) should be re-run unmodified as the proof |
| CASF-09 | Dual test strategy: fakeredis (fallback) + real Redis Stack (integration), honoring documented divergences | Pitfall 3 + Environment Availability confirm no new fakeredis-side code is needed; Recommended Project Structure names the new integration test file mirroring `test_cascade_graph_shapes.py`/`test_cascade_depth_and_gate.py` |
| CASF-10 | Docs (site + docstrings) extended with the two new shapes, coverage matrix updated | Open Question 2 + Assumption A3 clarify that no literal "coverage matrix" table exists yet in `ttl-cascade.md` — the plan should add one; Recommended Project Structure names the doc file to extend |
</phase_requirements>

## Summary

Phase 2 is a small, surgical extension to one file (`rapyer/scripts/lua/cascade/library.lua`) plus test fixtures and docs — no new dependencies, no Python-side production code changes. Phase 1 already shipped the `CascadeEdge.sf_container` discriminator ("set"/"zset") and the `path` field holding the bare SF-field-name suffix; Phase 2's entire job is teaching the Lua `push_edges` walk to branch on `edge.sf_container`, read the field's own Redis key with `SMEMBERS`/`ZRANGE key 0 -1`, decode each member, and feed the decoded target-key string into the existing `push_child`/`next_hop`/`visited` machinery — exactly as an inline collection-of-FK edge already does.

**The single most important, non-obvious finding of this research (empirically verified against a running real Redis 7.4.7, not just read from source): both `RedisSet` and `RedisPriorityQueue` store their `ForeignKey` members as JSON-encoded (double-quoted) strings, not bare key strings.** `SMEMBERS`/`ZRANGE` return e.g. `"CascadeAuthor:abc-123"` (17 characters, including the two literal `"` characters), not `CascadeAuthor:abc-123`. This contradicts the CONTEXT.md/STATE.md working assumption ("assuming SMEMBERS/ZRANGE return the plain target-key strings") for **both** container kinds — earlier planning notes suspected this only for the priority queue. Each member must be unwrapped with `cjson.decode(member)` before it can be pushed into the traversal (verified that Redis's bundled cjson correctly decodes a bare JSON string scalar, e.g. `cjson.decode('"CascadeAuthor:abc-123"')` → `CascadeAuthor:abc-123`).

The second key finding: **SF edges must NOT be folded into the existing `read_reference_paths`/single-`JSON.GET` batch.** `edge.path` for an SF edge is a bare field name (e.g. `"refs"`), not a `$.`-rooted JSONPath. Empirically verified against real RedisJSON: a batched `JSON.GET key $.author refs` call does **not** error — it silently returns `{"refs":[],...}` (empty match) for the bare-name path — so a class whose *only* cascade edge is an SF edge would silently never read its container if the SF edge were folded into the same batch. A dedicated branch, keyed on `edge.sf_container`, that issues its own `SMEMBERS`/`ZRANGE` call is required, exactly as CONTEXT.md's Claude's-Discretion note anticipated.

Everything else — depth-budget semantics, cycle-safety via the best-budget-per-node `visited` map, the write-phase EXPIRE loop, dangling-count tallying, and the real-Redis-Function-only / fakeredis-root-own-EXPIRE-fallback split — is unchanged and reused verbatim; Phase 1 already made the plan-table shape (`is_collection=True`, same `entry.fks` list) carry these semantics for free.

**Primary recommendation:** Add a dedicated `edge.sf_container` branch inside `push_edges` (not a separate function) that, per SF edge, computes `follow/budget` via the existing `next_hop` once, and — only if `follow` — issues one `SMEMBERS` or `ZRANGE key 0 -1`, decodes every member with `cjson.decode`, and calls `push_child(decoded_key, edge, budget)` for each. Keep the existing single-`JSON.GET` batch path for non-SF edges completely unchanged (filter SF edges out of the `paths` list that feeds it).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SF-container member read (`SMEMBERS`/`ZRANGE`) | Database/Storage (Redis Function, runs server-side inside Redis) | — | The Redis Function executes *inside* the Redis process; this is a DB-tier read, not an application-tier round trip |
| Member decode (`cjson.decode` unwrap) | Database/Storage | — | Must happen in the same Lua execution as the read (atomicity requirement); no Python-side involvement |
| Cycle-safety / best-budget-per-node `visited` | Database/Storage | — | Existing `library.lua` machinery, reused unchanged; SF edges are just another edge kind feeding it |
| Depth-budget bookkeeping (`next_hop`) | Database/Storage | — | Pure Lua closure state, per-call, reused unchanged |
| Atomic EXPIRE apply + dangling-count tally | Database/Storage | API/Backend (result surfaced via `CascadeResult`) | Write phase runs in Redis; the `[dangling_children, dangling_special]` return value is unpacked into `CascadeResult` in `rapyer/base.py` |
| fakeredis fallback (root-own `EXPIRE`) | API/Backend | — | Pure Python branch in `AtomicRedisModel.refresh_ttl`/`aset_ttl` (`Meta.is_fake_redis` check); no Lua involved at all |
| Static plan classification (`sf_container`, `path`, `depth`) | API/Backend | — | Already shipped in Phase 1 (`rapyer/cascade/planner.py`); Phase 2 only *consumes* this, does not change it |

No Browser/Client, Frontend-Server(SSR), or CDN/Static tier is implicated — this is a pure backend/data-layer library.

## Standard Stack

### Core

No new libraries are introduced by this phase. The existing stack is reused as-is:

| Library | Version (verified) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| redis (redis-py) | 7.0.1 (installed, `pyproject.toml` pins `>=6.0.0,<8.1.0`) [VERIFIED: `python3 -c "import redis; print(redis.__version__)"`] | Async client, `pipeline.fcall(...)` | Already the project's sole Redis client; `Redis.fcall(function, numkeys, *keys_and_args)` signature confirmed via `inspect.signature` [VERIFIED: local introspection] |
| Redis Stack / Redis Functions | 7.4.7 standalone, RedisJSON present, running on `localhost:6370` [VERIFIED: `redis-cli -p 6370 info server`] | Server-side Lua execution (`FUNCTION LOAD`/`FCALL`), `SMEMBERS`, `ZRANGE`, `cjson` | Existing v1.3.5 backbone; no version bump needed — Redis 7+ already required for the cascade Function |
| fakeredis[lua,json] | 2.34.1 [VERIFIED: `uv.lock`] | Unit-test double; does NOT implement Redis Functions | Confirms the D-01 status-quo split: cascade Function code (including the new SF branch) never executes on fakeredis |

**No installation step required** — this phase edits `library.lua`, test fixtures, and docs only.

**Version verification:** `redis-cli -p 6370 info server` → `redis_version:7.4.7`, `redis_mode:standalone` [VERIFIED, ran against the actual dev instance]. `python3 -c "import redis; print(redis.__version__)"` → `7.0.1` [VERIFIED]. `uv.lock` pins `fakeredis==2.34.1` [VERIFIED].

### Supporting

None — no new supporting libraries.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `cjson.decode(member)` to unwrap the JSON-quoted member | Manual `string.sub`/pattern-based quote-stripping | `cjson.decode` correctly handles any JSON-escaped character a key could theoretically contain (backslash, embedded quote); manual stripping is faster but fragile and untested for edge cases. Both were empirically verified to work for the plain-ASCII-key case; `cjson.decode` is the safer, already-idiomatic choice (the file already uses `cjson.decode` pervasively) |
| Dedicated `edge.sf_container` branch inside `push_edges` | A separate top-level `push_sf_edges(...)` function called alongside `push_edges` | Functionally equivalent; keeping it as a branch inside the same loop that already iterates `fk_edges(parent_class)` avoids iterating the edge list twice and keeps the "one edge list, branch per shape" structure `push_edges` already uses (`is_collection` branch) |

## Package Legitimacy Audit

**Not applicable — this phase introduces no new external packages.** No `pip install`/`npm install`/Lua-module dependency is added; the only file with net-new logic is `rapyer/scripts/lua/cascade/library.lua` (bundled with the project, not a package), plus Python test fixtures and Markdown docs. The Package Legitimacy Gate protocol is skipped per its own scope ("whenever this phase installs external packages").

## Architecture Patterns

### System Architecture Diagram

```
Parent.asave() / aset_ttl(cascade=True) / refresh_ttl()
        |
        v
rapyer/base.py: scripts_registry.run_fcall(pipe, cascade_function_name, 1, root_key, root_class, "__rapyer_special__", ttl, do_cascade)
        |
        v  (pipeline.fcall queued; executed on pipe.execute())
====================== Redis process (server-side, atomic) ======================
cascade_apply(keys, args)                      <-- library.lua, ONE FCALL, ONE atomic op
  |
  |-- plan_refresh_keys()  [READ phase, no Redis writes]
  |     |
  |     |-- queue_refresh(root_key) + queue_special_refresh(root_key)
  |     |-- push_edges(root_key, root_class, UNBOUNDED, established=false)
  |     |       for each edge in fk_edges(root_class):
  |     |         if edge.sf_container == nil:                          <-- INLINE edge (unchanged)
  |     |             batch into `paths`; ONE JSON.GET for all inline edges of this node
  |     |         else:                                                  <-- NEW: SF edge branch
  |     |             (follow, budget) = next_hop(edge, remaining_budget, established)
  |     |             if follow:
  |     |                 sf_key = special_prefix .. ':' .. parent_key .. ':' .. edge.path
  |     |                 members = SMEMBERS(sf_key)  or  ZRANGE(sf_key, 0, -1)
  |     |                 for each raw_member in members:
  |     |                     target_key = cjson.decode(raw_member)      <-- unwrap the JSON-quoted string
  |     |                     push_child(target_key, edge, budget)       <-- SAME as inline collection edge
  |     |
  |     |-- while #stack > 0: pop frame, queue_refresh/queue_special_refresh,
  |     |     recurse via push_edges(child_key, child_class, child_budget, established=true)
  |     |     (identical for a child reached via an inline edge OR an SF edge)
  |     |
  |     `-- returns refresh_order (deduped, ordered list of {key, class, is_root, is_special})
  |
  `-- WRITE phase (only place EXPIRE appears) -- UNCHANGED by this phase
        for each queued item: EXPIRE(item.key, item.is_root and root_ttl or PLAN[item.class].ttl)
        tally dangling_children_count / dangling_special_count on a 0-return (missing key)
        return {dangling_children_count, dangling_special_count}
===================================================================================
        |
        v
rapyer/base.py: results[-1] -> CascadeResult(dangling_children=..., dangling_special=...)
```

### Recommended Project Structure

No new files/directories — this phase edits in place:

```
rapyer/scripts/lua/cascade/
└── library.lua              # push_edges() gains the edge.sf_container branch; everything else unchanged

tests/models/
└── cascade_types.py         # + new fixtures for CASF-07 hard shapes (self-ref-in-SF, diamond-via-SF, shared inline+SF child)

tests/unit/cascade/
├── conftest.py               # register new fixtures in CASCADE_PLANNER_MODELS if used by a fakeredis-fallback test
└── test_<new>.py             # fakeredis fallback proof (D-01): root-own-EXPIRE, no traversal

tests/integration/foreign_keys/
├── conftest.py                            # reuse setup_real_redis_for_cascade_apply (already parameterized over ALL_CASCADE_MODELS)
└── test_cascade_sf_held_ref_apply.py       # NEW: real-Redis :6370 reach proof, mirrors test_cascade_graph_shapes.py / test_cascade_depth_and_gate.py

docs/documentation/special-fields/
└── ttl-cascade.md            # extend with the two new shapes + worked example + fakeredis-divergence note (CASF-10)
```

### Pattern 1: Branch-per-edge-shape inside a single node-walk loop

**What:** `push_edges` already branches on `edge.is_collection` vs scalar inside one loop over `fk_edges(parent_class)`. The SF read is a third branch, keyed on `edge.sf_container`, inside the SAME loop — not a second pass over the edge list, not a second function.

**When to use:** Any time a new edge *shape* needs a different Redis read strategy but must still terminate in the same `push_child`/`visited` call.

**Example (illustrative Lua sketch — verify exact syntax during implementation):**
```lua
-- Source: rapyer/scripts/lua/cascade/library.lua:233 (push_edges), extended
local function push_edges(parent_key, parent_class, remaining_budget, established)
    local edges = fk_edges(parent_class)
    if #edges == 0 then
        return
    end
    local paths = {}
    local inline_edges = {}
    for _, edge in ipairs(edges) do
        if edge.sf_container then
            -- NEW: SF-held-ref edge. Compute follow/budget ONCE per edge (not
            -- per member) exactly like the existing collection-edge branch does.
            local follow, budget = next_hop(edge, remaining_budget, established)
            if follow then
                if not edge.recurse_into_target then
                    budget = 0  -- mirrors the existing dead-but-documented seam
                end
                local sf_key = special_prefix .. ':' .. parent_key .. ':' .. edge.path
                local members
                if edge.sf_container == 'set' then
                    members = redis.call('SMEMBERS', sf_key)
                else -- 'zset'
                    members = redis.call('ZRANGE', sf_key, 0, -1)
                end
                for _, raw_member in ipairs(members) do
                    -- Members are stored JSON-encoded (quoted) by BOTH RedisSet
                    -- and RedisPriorityQueue -- verified empirically, see
                    -- Common Pitfalls. cjson.decode unwraps the quotes.
                    local ok, target_key = pcall(cjson.decode, raw_member)
                    if ok and type(target_key) == 'string' then
                        push_child(target_key, edge, budget)
                    end
                end
            end
        else
            paths[#paths + 1] = edge.path
            inline_edges[#inline_edges + 1] = edge
        end
    end
    if #paths > 0 then
        -- UNCHANGED: single JSON.GET batch, now containing ONLY inline edges.
        local values_by_path = read_reference_paths(parent_key, paths)
        for _, edge in ipairs(inline_edges) do
            local matched = values_by_path[edge.path]
            -- ... rest identical to current code (library.lua:244-278)
        end
    end
end
```

### Anti-Patterns to Avoid

- **Folding `edge.path` for an SF edge into the same `paths` array fed to `read_reference_paths`:** Empirically verified this does NOT crash — RedisJSON silently returns an empty match (`{"refs":[]}`) for a bare (non-`$.`) legacy path when the call has *other* valid paths, and returns a `redis.pcall` error (gracefully swallowed, also empty) when it is the *only* path. Either way, the SF container is **silently never read** — a correctness bug that no exception surfaces. Always route SF edges to their own `SMEMBERS`/`ZRANGE` call.
- **Treating `SMEMBERS`/`ZRANGE` output as ready-to-use target-key strings:** Both are JSON-encoded (quoted). Skipping `cjson.decode` means `push_child` receives a string like `"CascadeAuthor:abc-123"` (with literal quote characters) which will never match any real Redis key, silently breaking traversal into every SF-held child without ever raising an error.
- **Computing `next_hop` per-member instead of per-edge:** Would give every member of the same SET/ZSET a potentially different budget depending on call order artifacts; the correct model (already used for inline collections) is one `follow/budget` decision per **edge**, applied identically to every member.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON-string unwrapping of a quoted scalar | Manual `string.sub(s, 2, -2)` quote-stripping | `cjson.decode(member)` | Correctly handles any JSON escaping a key could theoretically carry; the file already relies on `cjson.decode` everywhere else (plan decode, `read_reference_paths`) — one decode idiom, not two |
| Cycle-safety / best-budget-per-node dedup for SF-reached children | A second `visited`-like table scoped to SF traversal | The existing `visited` map + `push_child`/`budget_is_larger` | Explicitly required by Phase 1 D-03a: a child reachable both inline and via an SF container must dedup through the SAME map so it's walked at the larger of the two budgets |
| Dangling-count tracking for SF-reached children | A new `dangling_sf_count` return slot | The existing `dangling_children_count` tally in the write-phase EXPIRE loop | Explicit D-02: a missing SF-reached child's key makes `EXPIRE` a cheap no-op, already tallied identically to any other reached child; no `CascadeResult` shape change |

**Key insight:** every piece of "hard" logic this phase might be tempted to duplicate (cycle safety, budget arithmetic, dangling counting) is already generic over "any reached child," because Phase 1 deliberately put the SF edge into the same `entry.fks` list an inline edge lives in. The only genuinely new code is the SF *read* (SMEMBERS/ZRANGE + decode) — everything downstream of `push_child` is 100% reused.

## Common Pitfalls

### Pitfall 1: Assuming SF container members are bare target-key strings

**What goes wrong:** A Lua implementation that does `push_child(raw_member, edge, budget)` directly (no decode) will push a string like `'"CascadeAuthor:abc-123"'` (with literal quote characters) into `push_child`. `visited`/`stack` will track this bogus key; the later `EXPIRE` write-phase will `EXPIRE` a key that never existed (a cheap no-op, silently inflating `dangling_children_count`) instead of the real target. **The real child's TTL is never refreshed** — a silent correctness failure, not a crash.

**Why it happens:** `ForeignKey`'s own pydantic serializer returns a bare string (`value._target_key`), which is what inline JSON-document storage uses — so it's natural to assume the same bare-string shape applies to SF-container storage. It doesn't: `RedisSet.__get_pydantic_core_schema__`'s `_serialize_wrap` and `RedisPriorityQueue._dump_member` both additionally `json.dumps()` each member before it reaches Redis (`RedisSet._dump_members` → `_adapter.dump_python(..., mode="json", context={REDIS_DUMP_FLAG_NAME: True})` routes through the wrap-serializer that does `[json.dumps(m) for m in base]`; `RedisPriorityQueue._dump_member` explicitly does `json.dumps(serialized)`).

**How to avoid:** Always `cjson.decode(raw_member)` before treating a SET/ZSET member as a target key. Verified empirically end-to-end (real Redis, real model instances): `SMEMBERS` on a `RedisSet[Reference[Author]]`'s key and `ZRANGE ... 0 -1` on a `RedisPriorityQueue[Reference[Author]]`'s key both return `'"Author:<uuid>"'` (with quotes); `redis.call` inside a Lua `EVAL` on the same Redis instance confirms `cjson.decode` on that string yields the bare `Author:<uuid>`.

**Warning signs:** A SET/ZSET-held cascade child's TTL never refreshes even though the edge is enabled and the depth budget is sufficient; `dangling_children_count` is non-zero even when every target genuinely exists.

### Pitfall 2: Folding the SF edge's `path` into the shared `JSON.GET` batch

**What goes wrong:** A class whose only cascade edge is an SF-held-ref edge (e.g. `CascadeSetRefParent`, `CascadeSetRefRootNoTtl`) never has its container read at all — no error, no test failure signal beyond an assertion that specifically checks the SF child's TTL.

**Why it happens:** `push_edges`'s existing structure collects every edge's `.path` into one `paths` array for a single batched `JSON.GET`. An SF edge's `path` is a bare field name (`"refs"`), not a `$.`-rooted JSONPath. Verified against real RedisJSON: `JSON.GET key $.author refs` (mixed valid + bare path) returns `{"refs":[],"$.author":["Author:1"]}` — no error, just an empty match for the bare path. A single-path call with only the bare name (`JSON.GET key refs`) does raise (`ERR Path '$.refs' does not exist`), which `read_reference_paths`'s `redis.pcall` swallows into an empty map — also silent.

**How to avoid:** Filter `edges` at the top of `push_edges`: edges with `edge.sf_container ~= nil` never enter the `paths` array; they get their own `SMEMBERS`/`ZRANGE` call in a separate branch (see Pattern 1).

**Warning signs:** A test asserting `CascadeSetRefParent`'s (or `CascadePQRefParent`'s) reached child TTL never passes even after implementing the read branch elsewhere — check that the SF edge's path never leaked into `paths`.

### Pitfall 3: Assuming fakeredis needs any new handling for SF edges

**What goes wrong:** Spending effort writing a fakeredis-side traversal fallback, or special-casing SF-held models in `refresh_ttl`/`aset_ttl`.

**Why it happens:** It's tempting to think "the new feature needs new backend-parity work." It doesn't: `refresh_ttl`/`aset_ttl` already gate on `self.Meta.is_fake_redis` **before** checking `_contains_foreign_key()` (verified: `rapyer/base.py:257-262` and `:609-613` — `if self.Meta.is_fake_redis or not self._contains_foreign_key(): ... pipe.expire(...)`). This is unconditional per-model, independent of whether the model has SF-held-ref edges, inline edges, or none. SF-held-ref models need zero new code on the fakeredis path.

**How to avoid:** Confirm (as this research did) that `CascadeSetRefParent`/`CascadePQRefParent` are already listed in `tests/unit/cascade/conftest.py`'s `CASCADE_PLANNER_MODELS` (they are, added in Phase 1) — the fakeredis proof for CASF-09 is "assert `run_fcall` is never called and `pipe.expire` is called for the root's own keys," identical in shape to the existing `test_refresh_ttl_cascade_branch.py` tests, just parametrized onto the SF fixtures.

**Warning signs:** A PR that touches `rapyer/base.py` or adds a `Meta.is_fake_redis` branch anywhere — this phase's change surface should be `library.lua` + tests + docs only (D-01/D-01a explicitly reject a Python-side fallback).

## Code Examples

### Assembling the SF container's Redis key (verified identical on both sides)

```python
# Source: rapyer/types/special.py:24-27 (Python side)
@classmethod
def special_field_key(cls, model_key: str, field_path: str) -> str:
    path = field_path
    clean_name = path.lstrip(".")
    return f"{SPECIAL_FIELD_KEY_PREFIX}:{model_key}:{clean_name}"
```

```lua
-- Source: rapyer/scripts/lua/cascade/library.lua:200 (Lua side, existing
-- special_suffixes refresh pass -- same assembly the new SF-read branch reuses)
queue_refresh(special_prefix .. ':' .. key .. ':' .. suffix, class_name, is_root, true)
```

Empirically verified end-to-end on real Redis: a `CascadeSetRefParent` instance's `refs` field produces the key `__rapyer_special__:CascadeSetRefParent:<uuid>:refs`, matching `special_prefix .. ':' .. parent_key .. ':' .. edge.path` exactly (`edge.path == "refs"` for this top-level field, per Phase 1's `_static_walk_sf_fk_edges`).

### `next_hop` / `push_child` — reused verbatim, no signature change

```lua
-- Source: rapyer/scripts/lua/cascade/library.lua:98-132, 204-224 (unchanged)
local function next_hop(edge, remaining_budget, established)
    -- ... existing budget arithmetic, unchanged
end

local function push_child(target_key, edge, budget)
    if type(target_key) == 'string' and budget_is_larger(budget, visited[target_key]) then
        visited[target_key] = budget
        stack[#stack + 1] = {
            key = target_key, class = edge.target, edge = edge,
            budget = budget, established = true,
        }
    end
end
```

An SF-reached child calls `push_child` with exactly the same three arguments an inline collection-of-FK edge would use — this is why no downstream code (cycle-safety, write-phase EXPIRE, dangling count) needs to change.

## State of the Art

| Old Approach (v1.3.5, pre-Phase-1) | Current Approach (post-Phase-1, this phase's starting point) | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `contains_fk_field()` returns `False` for SF types; SF-held FK references are invisible to the cascade planner | `_static_walk_sf_fk_edges` (Phase 1) emits a distinct `sf_container` edge for every cascade-enabled `RedisSet`/`RedisPriorityQueue` holding a `Reference[T]` | Phase 1 (2026-07-24, commit `f1b3498`) | The plan-table now carries the data Phase 2 needs; Phase 2 does zero Python-side classification work |
| `push_edges` reads only inline refs via one batched `JSON.GET` | (this phase) `push_edges` additionally branches per SF edge into a dedicated `SMEMBERS`/`ZRANGE` read | Phase 2 (in progress) | The cascade walker becomes a superset: every FK-shaped field (direct, collection, nested, SF-held) is now traversed |

**Deprecated/outdated:** None — this is additive, not a replacement of any existing mechanism.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `cjson.decode` behaves identically for this use case across all real-Redis versions the project supports (6.0–7.4 per CI matrix), not just the 7.4.7 instance tested here | Common Pitfalls / Code Examples | Low — `cjson` is a stable, long-unchanged bundled Lua library across Redis versions; however, Redis Functions (`FCALL`) themselves require Redis 7+, so the only versions where this branch ever executes are already 7+ (verified consistent with existing `requires_redis_functions` test gate) |
| A2 | The two new hard-shape fixtures needed for CASF-07 (self-reference held in a SET/PQ; a child reachable both inline AND via an SF container) do not yet exist in `tests/models/cascade_types.py` and must be added by the plan | Recommended Project Structure | Low — this is a planning gap, not a technical uncertainty; confirmed by reading the full fixture file, which has `CascadeSetRefParent`/`CascadePQRefParent`/`CascadeSetRefBlanket`/`CascadeSetRefOptOut` but no diamond/self-ref/shared-inline+SF fixture yet |
| A3 | The docs site's "cascade coverage matrix" referenced in CASF-10/D-04 does not exist as a literal table today — `docs/documentation/special-fields/ttl-cascade.md` currently documents shapes in prose, with no matrix table | Don't Hand-Roll / Recommended Project Structure | Low — the plan should either add a new table or treat "coverage matrix" as the doc's existing shape-enumeration; either satisfies CASF-10's intent, but the planner should decide explicitly rather than assume a table already exists to "extend" |

**Risk assessment:** All three assumptions are low-risk and don't affect the core Lua-branch design; A2/A3 are planning-scope clarifications (new fixtures/doc structure needed) rather than technical unknowns.

## Open Questions (RESOLVED)

1. **RESOLVED — Exact naming/placement of the two new hard-shape test fixtures for CASF-07**
   - What we know: `CascadeSetRefParent` → `CascadeAuthor` (simple SET reach) and `CascadePQRefParent` → `CascadeAuthor` (simple ZSET reach, depth=2) already exist and are registered in both `ALL_CASCADE_MODELS` and `tests/unit/cascade/conftest.py`'s `CASCADE_PLANNER_MODELS`. No fixture yet exists for (a) a self-reference held inside a SET/PQ, (b) a child reachable both via an inline FK edge and via an SF container edge at different depth budgets (the "diamond via mixed edge kinds" case CASF-07 requires).
   - What's unclear: Whether to add these as new classes in `cascade_types.py` (following the existing `CascadeMaxBudgetRoot`/`CascadeWR02*` naming convention) or reuse/extend an existing class.
   - Recommendation: Follow the existing fixture-naming convention (e.g. `CascadeSetRefSelfNode`, `CascadeMixedEdgeSharedChildRoot`) and register them in `ALL_CASCADE_MODELS` (for integration) — they don't need `CASCADE_PLANNER_MODELS` unless a fakeredis-fallback test also exercises them.

2. **RESOLVED — Whether the docs "coverage matrix" (CASF-10/D-04) should be a new literal table or an extension of the existing prose enumeration in `ttl-cascade.md`**
   - What we know: No literal matrix table exists today; the doc lists shapes in prose/section headers (per-field/global, direct FK, cascading refresh, cluster boundary).
   - What's unclear: The roadmap/REQUIREMENTS wording ("coverage matrix... updated to include the two new shapes") implies a pre-existing matrix, but none was found.
   - Recommendation: The plan should add a small table (e.g. `| Shape | Example | Cascade-eligible |`) enumerating direct FK / collection-of-FK / nested-submodel FK / `RedisSet[Reference[T]]` / `RedisPriorityQueue[Reference[T]]`, satisfying CASF-10's literal wording regardless of whether an implicit "matrix" existed before.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Real Redis Stack (standalone) at `localhost:6370` | Integration test proof (CASF-09 real-Redis leg), `requires_redis_functions` fixture | ✓ | 7.4.7, standalone, RedisJSON loaded [VERIFIED: `redis-cli -p 6370 info server`] | — (no fallback needed; this is the dev-standard instance per user memory) |
| fakeredis[lua,json] | Unit test proof (CASF-09 fakeredis leg) | ✓ | 2.34.1 [VERIFIED: `uv.lock`] | — |
| redis-py (async client) | `pipeline.fcall(...)` | ✓ | 7.0.1 [VERIFIED: `python3 -c "import redis; print(redis.__version__)"`] | — |
| `cjson` (bundled with Redis) | Member decode in the new Lua branch | ✓ | Bundled with Redis 7.4.7; behavior verified via `redis-cli -p 6370 eval` | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — everything required is already present and already the project's standard toolchain.

## Project Constraints (from CLAUDE.md)

No project-local `./CLAUDE.md` exists in this repository/worktree — only the user's global `~/.claude/CLAUDE.md` applies (context-explorer-first code discovery, `jbcontext search` conventions, general tooling preferences). None of its directives constrain the technical shape of this phase; it governs *how the assistant searches code*, not what code should look like. No project-specific coding-convention file overrides apply beyond the global Python style rules already reflected in this document (short docstrings, no unnecessary comments).

## Security Domain

`security_enforcement` is not set in `.planning/config.json` (absent = enabled per policy), so this section is included, scoped honestly to what actually applies.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | This is an internal server-side traversal Function; no auth surface is touched |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A — access control to Redis itself is unchanged by this phase |
| V5 Input Validation | Marginally | Target-key strings decoded via `cjson.decode` flow only into `redis.call('EXPIRE', key, ttl)` (a key argument, never interpolated into a Lua `redis.call` command string or `eval`'d) — same trust model the existing inline-FK traversal already uses for `read_reference_paths`'s decoded values. No new validation gap is introduced; `pcall(cjson.decode, ...)` guards against a malformed member crashing the whole atomic call (mirrors the existing `pcall(cjson.decode, raw)` pattern in `read_reference_paths`) |
| V6 Cryptography | No | N/A — no crypto surface |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed/corrupted SET or ZSET member (not valid JSON) crashing the whole atomic cascade call | Denial of Service | Wrap the decode in `pcall(cjson.decode, raw_member)`; on failure, skip that member (dead-end that member, don't abort the FCALL) — mirrors the existing `read_reference_paths` pattern of returning an empty match on any decode failure rather than propagating the error |
| A decoded member that is not a string (e.g. cjson decodes a JSON number/object) being pushed into `push_child` | Tampering (data integrity) | Guard with `type(target_key) == 'string'` before calling `push_child`, exactly as the existing scalar-FK branch already does (`if type(matched) == 'string' then push_child(matched, edge, budget) end`) |

This phase's threat surface is narrow: it operates entirely within an already-atomic, already-trusted server-side Redis Function on data the application itself wrote (SF container members are always produced by `ForeignKey`'s own serializer, never raw user input passed straight to Redis). The two mitigations above are defensive consistency with the existing codebase's own patterns, not new security requirements.

## Sources

### Primary (HIGH confidence — direct code reads and live verification in this session)

- `rapyer/scripts/lua/cascade/library.lua` — full read; exact line numbers for `read_reference_paths` (43), `next_hop` (98), `push_child` (204), `push_edges` (233), `special_suffixes` refresh (194-202), write-phase EXPIRE + dangling (323-345) all confirmed accurate against CONTEXT.md's anchors
- `rapyer/cascade/planner.py` — full read; confirmed `CascadeEdge.sf_container`/`path` shape and `_static_walk_sf_fk_edges` (lines 198-242) scope ("direct fields only... does NOT recurse into nested inline sub-models")
- `rapyer/types/redis_set.py`, `rapyer/types/priority_queue.py`, `rapyer/types/special.py`, `rapyer/types/foreign_key.py` — full reads; confirmed `special_field_key` assembly and traced the double-JSON-encoding path for both container kinds
- `rapyer/base.py` (lines 230-329, 590-670) — confirmed `is_fake_redis` gate precedes `_contains_foreign_key()` check in both `refresh_ttl` and `aset_ttl`
- `rapyer/init.py` — confirmed Function registration gated on `not is_fake_redis` at lines 92-101 (verbatim match to CONTEXT.md's anchor)
- `rapyer/scripts/registry.py`, `rapyer/scripts/loader.py` — confirmed `run_fcall`, `register_cascade_function`, `build_cascade_library` wiring; no changes needed for Phase 2
- Live verification against real Redis 7.4.7 at `localhost:6370` (`redis-cli`, ad-hoc `EVAL` scripts, and a full Python script using `init_rapyer`/`CascadeSetRefParent`/`CascadePQRefParent`): confirmed (a) both `RedisSet` and `RedisPriorityQueue` store JSON-quoted members, (b) `cjson.decode` unwraps them correctly, (c) the assembled SF key matches `special_prefix .. ':' .. key .. ':' .. suffix` exactly, (d) `SMEMBERS`/`ZRANGE` on a missing key return an empty table (no error), (e) a mixed-path `JSON.GET` silently no-ops on a bare-name path rather than erroring
- `tests/integration/foreign_keys/test_cascade_graph_shapes.py`, `test_cascade_depth_and_gate.py`, `conftest.py` — full reads; this is the exact test pattern (helper `_apply_cascade` + `fcall` + `real_redis_client.ttl(...)` assertions) Phase 2's new integration tests should mirror
- `tests/unit/cascade/conftest.py`, `test_refresh_ttl_cascade_branch.py` — confirmed `CascadeSetRefParent`/`CascadePQRefParent` are already registered in `CASCADE_PLANNER_MODELS`, and the exact mock-based pattern for proving the fakeredis fallback (`run_fcall` not called, `pipe.expire` called)
- `tests/models/cascade_types.py` — full read of relevant sections; confirmed which SF fixtures exist (`CascadeSetRefParent`, `CascadePQRefParent`, `CascadeSetRefBlanket`, `CascadeSetRefOptOut`, plus 3 fail-fast fixtures) and which hard-shape fixtures for CASF-07 do NOT yet exist
- `.planning/codebase/CONCERNS.md` — confirmed the documented fakeredis/real-Redis divergences (WRONGTYPE emulation gap, Redis-7+-only Function requirement) that CASF-09 must honor
- `docs/documentation/special-fields/ttl-cascade.md` — full read; confirmed current doc structure and that no literal "coverage matrix" table exists yet

### Secondary (MEDIUM confidence)

None required — every claim in this document was verified directly against the codebase or a live Redis instance in this session.

### Tertiary (LOW confidence)

None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; existing versions confirmed live (`redis-cli info`, `uv.lock`, `python3 -c "import redis"`)
- Architecture: HIGH — the exact Lua branch was derived by reading the real `push_edges` code and confirmed against live Redis behavior (JSON.GET mixed-path behavior, SMEMBERS/ZRANGE-on-missing-key behavior, cjson.decode-of-scalar behavior all empirically tested, not assumed)
- Pitfalls: HIGH — both flagged pitfalls (JSON-quoted members; batch-corruption of bare-name paths) were reproduced end-to-end against a live Redis instance with real model instances, not inferred from reading serializer code alone

**Research date:** 2026-07-25
**Valid until:** 30 days (stable internal library code; no external API surface to drift) — re-verify sooner only if the project bumps its Redis version floor or fakeredis version
