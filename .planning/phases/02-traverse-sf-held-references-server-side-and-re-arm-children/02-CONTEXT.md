# Phase 2: Traverse SF-held references server-side and re-arm children - Context

**Gathered:** 2026-07-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the server-side cascade traversal actually **follow** the SF-held-ref edges that Phase 1 classified into the plan. The Redis Function (`rapyer/scripts/lua/cascade/library.lua`) must, for each `sf_container` edge on a node, read that special-field's own Redis key — `SMEMBERS` for `sf_container="set"`, `ZRANGE key 0 -1` for `sf_container="zset"` — decode each member as a `ForeignKey` target-key string, and feed it through the existing `push_child` / `next_hop` / best-budget-per-node `visited` machinery so each reached child is re-armed to its **own `Meta.ttl`** in the same atomic write phase as inline-reached children. The apply layer (the EXPIRE loop, dangling-count) is **reused unchanged** — this is traversal-reach only.

Covers CASF-04..10: SET read (CASF-04), ZSET read (CASF-05), per-child own-`Meta.ttl` re-arm atomically at set-time (CASF-06), cycle-safety + depth budget through SF containers (CASF-07), byte-for-byte preservation of existing inline behavior (CASF-08), dual-backend proof (CASF-09), docs (CASF-10).

**Backend reality (verified in `rapyer/init.py:92-101`):** the cascade Function is registered **only when `not is_fake_redis`**. On fakeredis it is never loaded, so *no* child cascade runs there today (inline or SF) — only the root's own keys refresh. Phase 2 preserves this: the real SF reach is proven on real Redis Stack :6370 (Function path); fakeredis exercises the root-own-`EXPIRE` fallback and relies on Phase 1's static plan tests for classification.

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### This milestone's planning
- `.planning/PROJECT.md` §"Current Milestone: v1.3.6 Cascade Reach Through Special-Field References" — goal, scope (traversal-reach only), constraints, Key Decisions table
- `.planning/REQUIREMENTS.md` — CASF-04..10 (Phase 2's requirements); Future/Out-of-Scope boundaries
- `.planning/ROADMAP.md` — Phase 2 goal + success criteria; the Phase 1/2 split
- `.planning/phases/01-classify-sf-held-fk-references-into-the-cascade-plan/01-CONTEXT.md` — Phase 1 decisions D-01..D-04 (edge representation, discovery pass, depth semantics, fail-fast); the `sf_container` contract Phase 2 consumes
- `.planning/phases/01-classify-sf-held-fk-references-into-the-cascade-plan/01-01-SUMMARY.md` — what Phase 1 shipped (the `sf_container` discriminator, `_static_walk_sf_fk_edges`, fixtures) + the lazy-import cycle landmine

### v1.3.5/v1.3.6 cascade backbone (the code being extended)
- `rapyer/scripts/lua/cascade/library.lua` — **the primary file this phase edits.** `read_reference_paths` (~43, single-`JSON.GET` batch), `next_hop` (~98, follow/budget decision), `push_child` (~204, best-budget-per-node `visited`), `push_edges` (~233, per-node walk + `is_collection` branch ~258/264), `special_suffixes` EXPIRE refresh (~199), write phase EXPIRE + dangling counts (~323-345). New SF read branch (SMEMBERS/ZRANGE keyed on `edge.sf_container`) plugs in here; write phase reused unchanged.
- `rapyer/cascade/planner.py` — `CascadeEdge.sf_container` (set/zset discriminator + SF key suffix in `path`), `_static_walk_sf_fk_edges`, `build_cascade_plan`, `cascade_plan_json`, `register_cascade_function` / `CASCADE_FUNCTION_PREFIX` (~374-383)
- `rapyer/init.py` — cascade Function registration is `not is_fake_redis`-gated (~92-101); `is_fakeredis` (~19); `build_cascade_plan` + `validate_cascade_ttl_targets` call site (~84)
- `rapyer/scripts/registry.py` — `register_scripts` / `build_script_texts(is_fakeredis=...)`, `run_fcall` (~156); `rapyer/scripts/loader.py` (~82, "cascade never loads on fakeredis")
- `rapyer/types/redis_set.py`, `rapyer/types/priority_queue.py`, `rapyer/types/special.py`, `rapyer/types/foreign_key.py` — how SF members serialize (target-key strings under `__rapyer_special__:{model_key}:{suffix}`) and the SET/ZSET storage
- `rapyer/base.py` — `_special_field_names` / `_ttl_keys()` (root-own key set that fakeredis refreshes); **DO NOT EDIT** `__init_subclass__` (~404-446)

### Cascade semantics to preserve
- `.planning/PROJECT.md` §"Key Decisions" — per-child own-`Meta.ttl` cascading refresh, set-time-only, server-side traversal, Redis-Functions apply, best-budget-per-node visited map
- `.planning/codebase/CONCERNS.md` — documented fakeredis/real-Redis divergences the dual-test strategy must honor (CASF-09)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `push_child` / `next_hop` / the `visited` best-budget-per-node map (`library.lua:98/204`) — SF members feed straight in; cycle-safety, diamonds, inline+SF shared children, and self-refs in a set/PQ all dedup through the same map keyed on the resolved target-key string. No new cycle reasoning (Phase 1 D-03a).
- Write-phase EXPIRE loop + `dangling_children_count` (`library.lua:323-345`) — reused verbatim; SF-reached children re-arm to their owning class's baked-in `Meta.ttl` exactly like inline-reached children (D-02).
- `special_suffixes` refresh pass (`library.lua:199`) — already EXPIREs the SF **container** key; the new edge follows the container's **members**. Complementary, both emitted for the same field (Phase 1 D-02b) — must not double-count.

### Established Patterns
- Real-Redis Function path vs fakeredis root-own fallback is an established, gated divergence (`init.py:92-101`); Phase 2 extends the Function only, leaving the fallback semantics as-is (D-01).
- The inline-collection edge (`is_collection=True`) is the depth-budget model the SF hop mirrors (Phase 1 D-03): entering the SF field costs one hop; all members share the edge's budget.
- Dual test strategy: fakeredis unit (fallback + static plan) + real Redis Stack :6370 integration (actual reach) — the pattern v1.3.5 Phase 4 used for cross-model cascade proof.

### Integration Points
- `edge.sf_container` (set/zset) is the branch key in `push_edges`; the SF key is assembled as `special_prefix .. ':' .. key .. ':' .. suffix` (same shape as the `special_suffixes` refresh at `library.lua:200`).
- The Function is `FUNCTION LOAD`ed from `cascade_plan_json(plan)`; the new read branch is baked into `library.lua`, so the plan-JSON → Lua-literal → `FUNCTION LOAD` pipeline needs no new wiring shape (Phase 1 confirmed the edge round-trips).

</code_context>

<specifics>
## Specific Ideas

- Prove on real Redis :6370 across the hard shapes the roadmap enumerates: `RedisSet[ForeignKey]` re-arm, `RedisPriorityQueue[ForeignKey]` re-arm, a diamond, a child reachable both inline and via an SF container (must be walked at the larger budget), and a self-reference held in a set/PQ — each terminating and re-armed exactly as the shared budget/visited rules dictate.
- Regression: run the existing v1.3.5 TTL/cascade suites unmodified to prove CASF-08 (inline direct/collection/nested-submodel shapes, `Meta.ttl`/`refresh_ttl`, non-cascade models unchanged); non-SF plan bytes/hash already asserted stable in Phase 1.
- Docs example should show a `RedisSet[ForeignKey[T]]` (and/or PQ) parent with cascade enabled and the resulting per-child refresh, plus the one-line fakeredis divergence note.

</specifics>

<deferred>
## Deferred Ideas

- **Python-side fallback traversal for fakeredis** (rejected as D-01a) — revisit only if hermetic unit coverage of the reach logic becomes a hard requirement and the divergence risk is judged acceptable.
- **Separate SF-dangling counter / distinct SF-hop error subtype** — deferred (D-02; Phase 1 D-04a) unless real usage shows the generic count/message is confusing.
- **SF containers holding nested inline submodels** (vs direct `ForeignKey[T]` elements) — out of milestone scope (REQUIREMENTS "Future").
- **Save/update/delete cascade apply through SF-held refs** — explicitly out of this milestone (traversal-reach only; the `CascadeSave`/`CascadeDelete` seams).
- Prior v1.3.5 robustness advisories retained: cascade-function self-heal (#284), WR-02/WR-03 (test freeze-leak / init freeze not exception-safe).

</deferred>

---

*Phase: 2-traverse-sf-held-references-server-side-and-re-arm-children*
*Context gathered: 2026-07-25*
