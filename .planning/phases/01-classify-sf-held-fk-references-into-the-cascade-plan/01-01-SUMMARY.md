---
phase: 01-classify-sf-held-fk-references-into-the-cascade-plan
plan: 01
subsystem: cascade
tags: [cascade, ttl, redis-set, redis-priority-queue, foreign-key, planner]

requires: []
provides:
  - "CascadeEdge.sf_container discriminator (set/zset, defaults None, dropped from JSON)"
  - "_static_walk_sf_fk_edges: dedicated planner pass over _special_field_names"
  - "SF-held-ref test fixtures (per-field, blanket, opt-out, fail-fast ttl=None)"
affects: [phase-02-traverse-sf-held-references-server-side]

tech-stack:
  added: []
  patterns:
    - "SF-held-ref edges reuse the same entry.fks list as inline FK edges (no new plan-table shape)"
    - "Lazy in-function import of RedisSet/RedisPriorityQueue in planner.py to break a real import cycle"

key-files:
  created:
    - tests/unit/cascade/test_cascade_sf_held_ref_plan.py
  modified:
    - rapyer/cascade/planner.py
    - tests/models/cascade_types.py
    - tests/unit/cascade/conftest.py

key-decisions:
  - "sf_container is the last CascadeEdge field, defaulting to None, per D-01/D-01a"
  - "RedisSet/RedisPriorityQueue import must be lazy inside _static_walk_sf_fk_edges, not module-top: a real cycle exists (types.priority_queue -> types.special -> scripts.loader -> cascade.planner) that the plan's interfaces note incorrectly assumed was cycle-safe"
  - "The three deliberately ttl=None fail-fast fixtures need Meta.init_with_rapyer=False so they stay out of REDIS_MODELS and don't break unrelated init_rapyer() tests"

requirements-completed: [CASF-01, CASF-02, CASF-03]

duration: 8min
completed: 2026-07-24
---

# Phase 01 Plan 01: Classify SF-held FK references into the cascade plan Summary

**Static cascade planner now emits a distinct `sf_container` ("set"/"zset") edge for `RedisSet[Reference[T]]` / `RedisPriorityQueue[Reference[T]]` fields via a dedicated `_special_field_names` discovery pass, honoring field > global > off precedence and fail-fast ttl validation, with non-SF plan bytes byte-identical.**

## Performance

- **Duration:** ~8 min (960b57a to f1b3498)
- **Started:** 2026-07-24T19:11:04+03:00
- **Completed:** 2026-07-24T19:14:47+03:00
- **Tasks:** 3 (2 commits — Task 3 folded into Task 2's commit; see Deviations)
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- `CascadeEdge` gained an `sf_container: str | None = None` discriminator (last field, dropped by `_drop_none_values`/`cascade_plan_json` for non-SF edges — non-SF plan hash unchanged)
- New `_static_walk_sf_fk_edges` pass in `rapyer/cascade/planner.py` discovers FK targets held inside `RedisSet`/`RedisPriorityQueue` fields via `_special_field_names` + `_unwrap_relational_target`, classifies enable/depth via `_classify_edge` (field > global > off), and appends the edge into the same `entry.fks` list the refresh-only special-suffix pass also covers (both mechanisms coexist for the same field)
- 7 new SF-held-ref fixtures in `tests/models/cascade_types.py`: 4 ttl-carrying (`CascadeSetRefParent`, `CascadePQRefParent`, `CascadeSetRefBlanket`, `CascadeSetRefOptOut`) registered in `ALL_CASCADE_MODELS`/`CASCADE_PLANNER_MODELS`, 3 deliberately ttl-less fail-fast fixtures (`CascadeSetRefNoTtlTarget`, `CascadeSetRefToNoTtl`, `CascadeSetRefRootNoTtl`) kept out of both lists and out of `REDIS_MODELS`
- 11 new unit tests in `tests/unit/cascade/test_cascade_sf_held_ref_plan.py` proving: edge shape for set/zset, coexistence with the refresh-only suffix, blanket/opt-out precedence, `sf_container` key-absence in non-SF JSON, `sf_container is None` on inline edges, fail-fast on a ttl-less SF target and on a root-with-only-SF-edges, a positive no-raise control, and a guard assertion for the `contains_fk_field()` premise
- Full `tests/unit/cascade` suite (75 tests) and the full `tests/unit` suite (813 tests) pass; `rapyer/base.py` diff is empty; no Lua files touched

## Task Commits

Each task was committed atomically (Task 3's tests were combined into Task 2's file/commit — see Deviations):

1. **Task 1: Add sf_container discriminator to CascadeEdge + SF-held-ref test fixtures** - `960b57a` (feat)
2. **Task 2 + 3: SF-held-ref discovery pass in build_cascade_plan + edge/precedence/hash-stability/fail-fast tests** - `f1b3498` (feat)

**Plan metadata:** (this commit, following SUMMARY)

## Files Created/Modified
- `rapyer/cascade/planner.py` - `CascadeEdge.sf_container` field + docstring; new `_static_walk_sf_fk_edges` pass wired into `build_cascade_plan`
- `tests/models/cascade_types.py` - 7 new SF-held-ref fixtures (4 ttl-carrying + 3 ttl-less fail-fast, all `init_with_rapyer=False` on the ttl-less ones)
- `tests/unit/cascade/conftest.py` - registered the 4 ttl-carrying fixtures in `CASCADE_PLANNER_MODELS`
- `tests/unit/cascade/test_cascade_sf_held_ref_plan.py` - new test file covering edge shape, precedence, hash stability, and fail-fast validation

## Decisions Made
- `sf_container` defaults to `None` and is the last `CascadeEdge` field (D-01/D-01a) — existing field order/positional constructors elsewhere in the test suite stay valid
- Module-top import of `RedisSet`/`RedisPriorityQueue` in `planner.py` is NOT cycle-safe, contrary to the plan's interfaces note; switched to a lazy in-function import (mirrors the existing `_unwrap_nested_model_cls` pattern) — see Deviations
- The three deliberately ttl-less fail-fast fixtures needed `Meta.init_with_rapyer=False` to stay out of the global `REDIS_MODELS` registry — see Deviations

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Module-top RedisSet/RedisPriorityQueue import reintroduces a real cycle**
- **Found during:** Task 2 (running the new test file — full test-suite import failed)
- **Issue:** The plan's interfaces note asserted a module-top import of `RedisSet`/`RedisPriorityQueue` into `planner.py` was cycle-safe. In practice: `rapyer.types.priority_queue` imports `rapyer.types.special`, which imports `rapyer.scripts.loader`, which imports `rapyer.cascade.planner` (for `cascade_names`/`cascade_plan_lua_literal`) — a real cycle when `planner.py` also imports `rapyer.types.priority_queue` at module load time. This broke `import rapyer` entirely (`ImportError: cannot import name 'load_sf_load_snippet' from partially initialized module`).
- **Fix:** Moved the `RedisSet`/`RedisPriorityQueue` imports into `_static_walk_sf_fk_edges` itself (lazy, in-function), exactly as the plan's own fallback instruction specified ("fall back to a lazy import inside the pass ONLY if a real cycle actually surfaces, mirroring the existing `_unwrap_nested_model_cls` lazy-import").
- **Files modified:** `rapyer/cascade/planner.py`
- **Verification:** `import rapyer` succeeds; full `tests/unit` suite (813 tests) passes.
- **Committed in:** `f1b3498` (Task 2 commit)

**2. [Rule 1 - Bug] ttl-less fail-fast fixtures broke unrelated init_rapyer() tests**
- **Found during:** Task 2/3 (running `tests/unit/cascade` in full — a pre-existing, unrelated `init_rapyer` cascade-ttl test started failing)
- **Issue:** `AtomicRedisModel.__init_subclass__` auto-registers every subclass into the global `REDIS_MODELS` list (unless `Meta.init_with_rapyer=False`). The three deliberately ttl-less fixtures (`CascadeSetRefNoTtlTarget`, `CascadeSetRefToNoTtl`, `CascadeSetRefRootNoTtl`) were therefore swept into `REDIS_MODELS`, and any test calling `init_rapyer()`/`build_cascade_plan(REDIS_MODELS)` + `validate_cascade_ttl_targets` over the full registry hit `CascadeTargetTtlMissingError` unexpectedly.
- **Fix:** Set `Meta.init_with_rapyer=False` on all three ttl-less fixtures (the established pattern already used elsewhere in the test suite, e.g. `tests/models/index_types.py`) so they're excluded from `REDIS_MODELS` and only ever participate via the explicit model lists the new unit tests pass to `build_cascade_plan([...])` directly.
- **Files modified:** `tests/models/cascade_types.py`
- **Verification:** Full `tests/unit/cascade` suite (75 tests) and full `tests/unit` suite (813 tests) pass.
- **Committed in:** `f1b3498` (Task 2 commit)

**3. [Process] Task 3's tests folded into the Task 2 commit**
- **Found during:** Task 2 implementation
- **Issue:** Task 2 and Task 3 both target the same new file (`tests/unit/cascade/test_cascade_sf_held_ref_plan.py`); writing it once with both the edge-shape/precedence/hash-stability tests (Task 2) and the fail-fast validation regression tests (Task 3) in a single pass was more efficient than a second edit-and-recommit cycle.
- **Fix:** Both tasks' acceptance criteria are met and independently verified in the single commit `f1b3498`; no code behavior differs from doing it as two commits.
- **Files modified:** `tests/unit/cascade/test_cascade_sf_held_ref_plan.py`
- **Committed in:** `f1b3498`

---

**Total deviations:** 3 (2 auto-fixed bugs, 1 process note — no scope creep)
**Impact on plan:** Both auto-fixes were necessary for correctness (import cycle would have broken `import rapyer` entirely; the REDIS_MODELS leak would have broken unrelated tests). No architectural changes; no plan re-scoping.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- The `CascadeEdge.sf_container` shape (SF key suffix in `path`, target class, "set"/"zset" kind, depth) is now the stable contract Phase 2's `library.lua` will branch on to read `SMEMBERS`/`ZRANGE` and follow the refs.
- `entry.fks` uniformly carries both inline and SF-held-ref edges, so `validate_cascade_ttl_targets` already covers SF targets with no further validator work needed in Phase 2.
- No blockers identified for Phase 2 (server-side traversal + dual-backend proof + docs).

---
*Phase: 01-classify-sf-held-fk-references-into-the-cascade-plan*
*Completed: 2026-07-24*

## Self-Check: PASSED

All created/modified files and both task commit hashes (960b57a, f1b3498) verified present.
