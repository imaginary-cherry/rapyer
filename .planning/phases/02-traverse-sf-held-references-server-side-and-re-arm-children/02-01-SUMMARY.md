---
phase: 02-traverse-sf-held-references-server-side-and-re-arm-children
plan: 01
subsystem: database
tags: [redis, lua, redis-functions, cascade-ttl, foreign-key, redis-set, redis-priority-queue]

# Dependency graph
requires:
  - phase: 01-classify-sf-held-fk-references-into-the-cascade-plan
    provides: "CascadeEdge.sf_container discriminator + _static_walk_sf_fk_edges static classification pass"
provides:
  - "push_edges SF-container read branch (SMEMBERS/ZRANGE) in library.lua, feeding the existing push_child/next_hop/visited machinery"
  - "Six new hard-shape test fixtures in tests/models/cascade_types.py (self-ref-in-SET/PQ, mixed inline+SF shared child, SF-only dual-edge diamond)"
  - "Real-Redis :6370 integration proof (test_cascade_sf_held_ref_apply.py, 8 tests) for CASF-04..08"
  - "Fix for self-referencing FK targets baked into SF-container generic args (ForwardRef resolution via global model registry)"
  - "Fix for RedisSet/RedisPriorityQueue._dump_members not validating raw FK input before serializing"
affects: [02-02, 02-03, 02-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lua push_edges branches per edge.sf_container: SF edges dispatch SMEMBERS/ZRANGE immediately per-node; inline edges stay batched through the single JSON.GET"
    - "SF member decode guarded with pcall(cjson.decode, raw_member) + type(target_key)=='string' check, mirroring the existing scalar-FK dead-end pattern"

key-files:
  created:
    - tests/integration/foreign_keys/test_cascade_sf_held_ref_apply.py
  modified:
    - rapyer/scripts/lua/cascade/library.lua
    - tests/models/cascade_types.py
    - rapyer/cascade/planner.py
    - rapyer/types/redis_set.py
    - rapyer/types/priority_queue.py

key-decisions:
  - "SF edges are dispatched synchronously inside the per-node push_edges loop (not batched); inline edges stay deferred to the post-loop batched JSON.GET — order-independent because visited-map max-budget-wins doesn't depend on arrival order"
  - "No separate SF-dangling counter — SF-reached dangling members reuse the existing dangling_children_count/dangling_special_count tally (D-02)"
  - "Self-referencing FK targets baked into an SF container's dynamic subclass generic args are resolved via a global-registry name lookup, since pydantic's model_rebuild(force=True) never reaches that opaque __orig_bases__ alias"

requirements-completed: [CASF-04, CASF-05, CASF-06, CASF-07, CASF-08]

# Metrics
duration: 25min
completed: 2026-07-26
---

# Phase 2 Plan 1: Traverse SF-held references server-side and re-arm children Summary

**Redis Function `push_edges` now reads RedisSet (SMEMBERS) and RedisPriorityQueue (ZRANGE) special-field keys server-side, decoding each JSON-quoted member and feeding it through the existing push_child/next_hop/visited machinery so SF-held FK targets re-arm to their own Meta.ttl atomically alongside inline-reached children.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3 completed
- **Files modified:** 5 (1 created)

## Accomplishments
- `library.lua`'s `push_edges` branches per `edge.sf_container`: SF edges read SMEMBERS/ZRANGE and decode members via a guarded `pcall(cjson.decode, ...)`; inline edges keep the single batched `JSON.GET` path unchanged and never see an SF edge's bare-name path.
- Six new hard-shape fixtures (`CascadeSetRefSelfNode`, `CascadePQRefSelfNode`, `CascadeMixedEdgeSharedChild(Root)`, `CascadeSfDiamondChild`/`CascadeSfDiamondRoot`) prove self-ref cycle-safety in both SMEMBERS and ZRANGE branches, max-budget-wins across mixed inline+SF edges, and dedup across two different SF-container kinds converging on one child.
- Real-Redis :6370 integration suite (8 tests, A-H) proves SET reach, PQ reach, dangling-count reuse, both self-ref terminations, mixed-edge max-budget-wins, malformed/non-string member tolerance, and SF-only dual-edge diamond convergence.
- Full pre-existing regression suite (`test_cascade_graph_shapes.py`, `test_cascade_depth_and_gate.py`, `tests/unit/cascade/`) passes with zero source modification — CASF-08 byte-for-byte proof.
- Two latent bugs, both only reachable once real SF-held FK writes were exercised for the first time in this codebase, were found and fixed (see Deviations).

## Task Commits

1. **Task 1: Add SF-held-ref hard-shape test fixtures** - `45082e1` (feat)
2. **Task 2: Implement the SF-container read branch in push_edges** - `7390594` (feat)
3. **Task 3: Real-Redis :6370 integration proof + regression pass** - `3761f50` (test, includes two blocking bug fixes)

_Note: Task 3's commit bundles the test file with two required bug fixes (`rapyer/cascade/planner.py`, `rapyer/types/redis_set.py`, `rapyer/types/priority_queue.py`) discovered while making the new tests pass — see Deviations below._

## Files Created/Modified
- `rapyer/scripts/lua/cascade/library.lua` - New `push_sf_edge` helper + `push_edges` split into SF (immediate SMEMBERS/ZRANGE dispatch) vs inline (batched JSON.GET) branches
- `tests/models/cascade_types.py` - Six new SF-held-ref hard-shape fixtures, registered in `ALL_CASCADE_MODELS`
- `tests/integration/foreign_keys/test_cascade_sf_held_ref_apply.py` - New: 8 tests (A-H) proving SF-held-ref reach on real Redis :6370
- `rapyer/cascade/planner.py` - `_resolve_forward_ref` helper resolving a self-referencing FK target's `ForwardRef` via the global model registry
- `rapyer/types/redis_set.py` - `_dump_members` validates raw input via the adapter before dumping, so FK elements are coerced to real `ForeignKey` instances before serialization
- `rapyer/types/priority_queue.py` - Same validate-before-dump fix as `redis_set.py`

## Decisions Made
- Kept the Lua's SF-edge dispatch inline inside `push_edges`'s single per-node loop rather than pre-collecting SF edges into a second pass — matches the plan's Anti-Patterns guidance (call `next_hop` once per edge, never per member) with minimal structural change.
- Added an early return when an edge list is entirely SF-held (`#paths == 0`), skipping an unneeded whole-document `JSON.GET` call — a small, safe efficiency addition consistent with the existing `#edges == 0` early-return pattern already in the function.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `_unwrap_relational_target` crashed on a self-referencing SF-container FK target**
- **Found during:** Task 3 (first real-Redis run of the new self-ref-in-SET/PQ fixtures)
- **Issue:** `RedisSet[Reference["CascadeSetRefSelfNode"]]`'s dynamic subclass bakes its generic args (`ForeignKey[ForwardRef('CascadeSetRefSelfNode')]`) into `__orig_bases__` at class-body-execution time, before the class name is bound. `resolve_relational_targets`'s `model_rebuild(force=True)` re-evaluates pydantic's own top-level field annotations but never touches this opaque, `__init_subclass__`-generated alias, so `_unwrap_relational_target` returned the raw `ForwardRef` object and `target_cls.__name__` raised `AttributeError`. This only surfaced now because no prior SF-held-ref fixture used a self-reference inside an SF container (Phase 1's fixtures all pointed at `CascadeAuthor`, defined earlier in the same module).
- **Fix:** Added `_resolve_forward_ref` to `rapyer/cascade/planner.py`, resolving the `ForwardRef`'s name against the global `REDIS_MODELS` registry (model names are already required to be globally unique).
- **Files modified:** `rapyer/cascade/planner.py`
- **Verification:** `build_cascade_plan` now resolves `CascadeSetRefSelfNode`'s `peers` edge to `target='CascadeSetRefSelfNode'`; Test D and Test G pass on real Redis.
- **Committed in:** `3761f50` (Task 3 commit)

**2. [Rule 1 - Bug] `RedisSet`/`RedisPriorityQueue._dump_members` crashed on a raw FK target-key string**
- **Found during:** Task 3 (first real `.aadd()`/`.apush()` call ever exercised against an FK-typed SF container in this codebase)
- **Issue:** `_dump_members` called `TypeAdapter.dump_python(...)` directly on raw native-Python input (e.g. `author.key`, a `RapyerKey` string) without validating it first. `dump_python` never validates — it only serializes — so `ForeignKey`'s `_serialize` function received a plain string instead of a `ForeignKey` instance and crashed with `AttributeError: 'RapyerKey' object has no attribute '_target_key'`. This was previously masked because every existing SF-typed field in the test suite held plain scalars (`str`/`float`), whose identity serializer tolerates unvalidated input by coincidence.
- **Fix:** Both `_dump_members` implementations now call `self._adapter.validate_python(...)` first (coercing raw keys/models into real `ForeignKey` instances via `ForeignKey`'s own validator, which already accepts str/model/dict) before dumping.
- **Files modified:** `rapyer/types/redis_set.py`, `rapyer/types/priority_queue.py`
- **Verification:** All 8 new integration tests pass; full test suite (`uv run pytest tests/`, 2433 passed / 205 skipped) confirms no behavior change for existing scalar-typed SF fields.
- **Committed in:** `3761f50` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 3, 1 Rule 1)
**Impact on plan:** Both fixes were required for this plan's own Task 3 acceptance criteria to pass — no scope creep beyond making the plan's mandated fixtures/tests actually work end-to-end on real Redis.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Server-side SF-held-ref traversal is proven end-to-end via direct `FCALL` on real Redis :6370. Plan 02-04 (Wave 2, depends on this plan) proves the same reach fires through the public API (`asave()`/`aset_ttl()`/`refresh_ttl()`).
- No blockers. The `_resolve_forward_ref` and `_dump_members` fixes are general-purpose and apply to any future SF-held-ref fixture, not just this plan's six.

---
*Phase: 02-traverse-sf-held-references-server-side-and-re-arm-children*
*Completed: 2026-07-26*

## Self-Check: PASSED

- FOUND: tests/integration/foreign_keys/test_cascade_sf_held_ref_apply.py
- FOUND: commit 45082e1
- FOUND: commit 7390594
- FOUND: commit 3761f50
