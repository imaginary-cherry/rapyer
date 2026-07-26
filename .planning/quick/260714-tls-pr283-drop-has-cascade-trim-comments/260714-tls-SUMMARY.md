---
phase: quick-260714-tls
plan: 01
subsystem: database
tags: [cascade, ttl, redis, lua, cleanup, comments]

# Dependency graph
requires:
  - phase: quick-260708-lku
    provides: unified cascade Lua script as sole traversal source of truth
provides:
  - AtomicRedisModel without dead _has_cascade ClassVar
  - init_rapyer without the _has_cascade-marking loop (fail-fast validation preserved)
  - refresh_ttl/aset_ttl with trimmed, essential-why comment blocks
affects: [pr-283-review]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - rapyer/base.py
    - rapyer/init.py
    - tests/unit/cascade/test_refresh_ttl_cascade_branch.py
    - tests/unit/cascade/test_cascade_action_boundary.py
    - tests/integration/foreign_keys/test_cascade_concurrent_mutation.py
    - tests/integration/foreign_keys/test_cascade_action_boundary.py

key-decisions:
  - "Removed _has_cascade entirely rather than deprecating it -- proven dead (written, never read) since aset_ttl/refresh_ttl unified onto the cascade Lua script"
  - "Deleted pure pass-through wrapper fixtures in the four affected test files rather than leaving empty pass-through fixtures around"

patterns-established: []

requirements-completed: []

# Metrics
duration: 12min
completed: 2026-07-14
---

# Quick Task 260714-tls: Drop dead `_has_cascade` state and trim TTL-cascade comments Summary

**Removed the dead `_has_cascade` ClassVar/marking-loop (PR #283 review) and condensed two over-long TTL-cascade comment blocks in `rapyer/base.py` to their essential why, with zero behavior change.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-14T21:26:00+03:00
- **Completed:** 2026-07-14T21:29:16+03:00
- **Tasks:** 2 completed
- **Files modified:** 7

## Accomplishments
- `_has_cascade` ClassVar removed from `AtomicRedisModel`; `init_rapyer`'s marking loop removed, collapsed to `validate_cascade_ttl_targets(build_cascade_plan(REDIS_MODELS))` for fail-fast config validation
- Six `_has_cascade` stash/restore fixture and assertion call sites stripped across four test files; three pure pass-through wrapper fixtures deleted in favor of the base fixtures they wrapped
- `refresh_ttl`'s 7-line comment block trimmed to 2 lines; `aset_ttl`'s ~10-line ARGV-semantics block trimmed to 1 line and its 4-line NOSCRIPT follow-up note trimmed to 1 line -- zero logic/ARGV/pipeline-pattern change

## Task Commits

1. **Task 1: Remove dead _has_cascade product state from production code and its six test call sites** - `fca51ad` (refactor)
2. **Task 2: Trim over-long TTL-cascade comment blocks in rapyer/base.py (comment text only)** - `d0d0890` (docs)

## Files Created/Modified
- `rapyer/base.py` - Removed `_has_cascade: ClassVar[bool] = False`; trimmed `refresh_ttl`/`aset_ttl` comment blocks (comment text only)
- `rapyer/init.py` - Removed the `_has_cascade`-marking loop; collapsed the two preceding lines to `validate_cascade_ttl_targets(build_cascade_plan(REDIS_MODELS))`
- `tests/unit/cascade/test_refresh_ttl_cascade_branch.py` - Removed `_STASH_MODELS`, `stash_has_cascade` autouse fixture, two `_has_cascade` assertions, unused `build_cascade_plan`/`CascadeChainNode` class imports
- `tests/unit/cascade/test_cascade_action_boundary.py` - Deleted `setup_fake_redis_for_action_boundary` pass-through fixture; `pytestmark` now points directly at `setup_fake_redis_for_cascade_apply`; removed unused `build_cascade_plan`/`CASCADE_PLANNER_MODELS`/`pytest_asyncio` imports; reworded a stale `_has_cascade=True` comment
- `tests/integration/foreign_keys/test_cascade_action_boundary.py` - Same pattern: deleted `setup_real_redis_for_action_boundary` pass-through fixture; `pytestmark` points at `setup_real_redis_for_cascade_apply`; removed unused imports
- `tests/integration/foreign_keys/test_cascade_concurrent_mutation.py` - Deleted `setup_real_redis_for_concurrent_mutation` pass-through fixture; removed its now-unneeded parameter from the one test that requested it; removed unused imports

## Decisions Made
- Removed `_has_cascade` entirely (not deprecated) -- grep confirmed it was write-only, no production read path depended on it.
- Deleted pure pass-through wrapper fixtures rather than leaving empty pass-throughs, per plan instruction, pointing tests directly at the base fixtures they had wrapped.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

PR #283 review round-2 items (dead `_has_cascade` state, verbose comment blocks) are resolved. Full suite green (2422 passed, 205 skipped, 0 failures) against real Redis Stack. No blockers for merge.

---
*Phase: quick-260714-tls*
*Completed: 2026-07-14*
