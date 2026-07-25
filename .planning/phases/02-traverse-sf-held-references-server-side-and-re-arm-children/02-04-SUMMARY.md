---
phase: 02-traverse-sf-held-references-server-side-and-re-arm-children
plan: 04
subsystem: database
tags: [redis, cascade-ttl, foreign-key, redis-set, redis-priority-queue, trigger-gate]

# Dependency graph
requires:
  - phase: 02-traverse-sf-held-references-server-side-and-re-arm-children
    plan: 01
    provides: "push_sf_edge SMEMBERS/ZRANGE branch in library.lua + SF-held-ref edge classification (sf_container discriminator) in build_cascade_plan / _static_walk_sf_fk_edges"
provides:
  - "class_declares_cascade_enabled_sf_ref_edge(model_cls) -- public planner predicate reusing _static_walk_sf_fk_edges's field>global>off classification"
  - "AtomicRedisModel._has_cascade_enabled_sf_ref_edge() lazily-cached classmethod + _contains_foreign_key() OR-fix, so refresh_ttl/aset_ttl/asave now fire the cascade Function for SF-only cascade-enabled parents"
  - "Mock-based unit proof (test_cascade_sf_only_trigger_gate.py) and real-Redis :6370 public-API proof (test_cascade_sf_held_ref_public_api.py) closing CASF-04/05/06"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazily-cached per-class classmethod populated via cls.__dict__ (not __init_subclass__), invoked at runtime well after every class's __init_subclass__ hook has already run -- avoids import-order/freeze-order concerns"
    - "Lazy (function-local) import used specifically to break a real module-init-time cycle between rapyer.cascade.planner and the rapyer.scripts package, matching the codebase's existing lazy-import cycle-breaking convention"

key-files:
  created:
    - tests/unit/cascade/test_cascade_sf_only_trigger_gate.py
    - tests/integration/foreign_keys/test_cascade_sf_held_ref_public_api.py
  modified:
    - rapyer/cascade/planner.py
    - rapyer/base.py

key-decisions:
  - "class_declares_cascade_enabled_sf_ref_edge builds a throwaway CascadeEdge list via _static_walk_sf_fk_edges rather than re-implementing classification, so it never needs to be kept in sync with a second implementation"
  - "_has_cascade_enabled_sf_ref_edge's import of the new planner helper is a lazy (function-local) import, not module-top -- a real cycle exists (planner -> scripts.constants -> rapyer.scripts package init -> registry -> loader -> back to planner) that only surfaces when rapyer.base itself triggers the planner import at module-init time; the plan's interfaces section assumed this was cycle-safe and was wrong"
  - "_contains_foreign_key() is the single central gate change; both refresh_ttl and aset_ttl (and asave via refresh_ttl_if_needed) inherit the fix with no per-call-site edit"

requirements-completed: [CASF-04, CASF-05, CASF-06]

# Metrics
duration: 35min
completed: 2026-07-26
---

# Phase 2 Plan 4: Fix the model-level cascade-trigger gate for SF-only parents Summary

**`_contains_foreign_key()` now OR-includes a lazily-cached, cascade-enablement-aware SF-held-ref check, so `asave()`/`aset_ttl(cascade=True)`/`refresh_ttl()` actually invoke 02-01's Lua traversal for parents whose sole cascade edge is an SF-held-ref field -- proven end-to-end via the public API on real Redis :6370.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 2 completed
- **Files modified:** 2 modified, 2 created

## Accomplishments
- `rapyer/cascade/planner.py` gained `class_declares_cascade_enabled_sf_ref_edge(model_cls)`, a public predicate that builds a throwaway edge list via the existing `_static_walk_sf_fk_edges` and returns whether any edge is SF-held -- reusing the exact field>global>off precedence `build_cascade_plan` already bakes into the Lua plan table, so a cascade-disabled SF-of-FK model (`CascadeSetRefOptOut`) is provably still `False`.
- `rapyer/base.py` gained a lazily-cached `_has_cascade_enabled_sf_ref_edge()` classmethod (cached on `cls.__dict__`, not via `__init_subclass__`) and `_contains_foreign_key()` now ORs it in as the single centralized gate change. Both `refresh_ttl` and `aset_ttl` (and therefore `asave()`, which calls `refresh_ttl_if_needed`) inherit the fix automatically.
- `contains_fk_field()` and `__init_subclass__` are byte-for-byte unmodified -- confirmed via `git diff` against the plan's base commit showing zero touched lines in either.
- Mock-based unit proof (`test_cascade_sf_only_trigger_gate.py`, 3 tests) proves `run_fcall` fires for `CascadeSetRefParent`/`CascadePQRefParent` and `pipe.expire` still fires (not `run_fcall`) for the cascade-disabled `CascadeSetRefOptOut`.
- Real-Redis :6370 integration proof (`test_cascade_sf_held_ref_public_api.py`, 3 tests) proves `asave()` and `aset_ttl(ttl, cascade=True)` re-arm an SF-held child's own `Meta.ttl` through the literal public API, with zero `_apply_cascade`/`run_fcall`/direct-FCALL calls anywhere in the test file (`grep -c "fcall\|_apply_cascade"` == 0).
- Full `tests/unit/` (818 tests) and `tests/integration/` (1623 passed / 205 skipped) suites pass with no regressions.

## Task Commits

1. **Task 1: Cascade-enablement-aware trigger gate + mock-based unit proof** - `2386b30` (feat)
2. **Task 2: Real-Redis :6370 public-API integration proof** - `7e3e32a` (test)

## Files Created/Modified
- `rapyer/cascade/planner.py` - New `class_declares_cascade_enabled_sf_ref_edge(model_cls)` public predicate, placed immediately after `_static_walk_sf_fk_edges`
- `rapyer/base.py` - New `_has_cascade_enabled_sf_ref_edge()` lazily-cached classmethod; `_contains_foreign_key()` now ORs it in; new function-local (lazy) import of the planner helper inside the classmethod
- `tests/unit/cascade/test_cascade_sf_only_trigger_gate.py` - New: 3 mock-based tests (True case x2, unchanged-False case) mirroring `test_refresh_ttl_cascade_branch.py`'s pattern
- `tests/integration/foreign_keys/test_cascade_sf_held_ref_public_api.py` - New: 3 tests (A-C) proving `asave()`/`aset_ttl(cascade=True)` re-arm SF-held children on real Redis :6370, public-API only

## Decisions Made
- Kept the new planner predicate a thin wrapper around `_static_walk_sf_fk_edges` rather than a bare structural "is this a RedisSet-of-ForeignKey?" check, so the cascade-disabled-opt-out case is correctly handled without a second classification implementation to maintain.
- Used a lazy (function-local) import for the planner helper inside `_has_cascade_enabled_sf_ref_edge`, per the codebase's existing convention for breaking real import cycles (see Deviations below for why this was required, not optional).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan's assumed-safe top-level import created a real module-init-time cycle**
- **Found during:** Task 1, first attempt to `import rapyer.base` after adding a top-level `from rapyer.cascade.planner import class_declares_cascade_enabled_sf_ref_edge` to `rapyer/base.py` as the plan's `<action>` literally specified.
- **Issue:** The plan's `<action>` asserted this import was "verified safe" because `planner.py`'s own module-level imports have "zero transitive dependency back on `rapyer.base`". That's true, but incomplete: `planner.py` imports `rapyer.scripts.constants`, and importing any submodule of `rapyer.scripts` first executes `rapyer/scripts/__init__.py`, which imports `registry.py`, which imports `loader.py`, which imports `rapyer.cascade.planner` (`cascade_names`, `cascade_plan_lua_literal`) -- back into the very module still being initialized. When `rapyer.base` is the very first module to trigger a `rapyer.cascade.planner` import (the normal case for any fresh Python process importing `rapyer`), this closes a real cycle: `base -> planner -> scripts.constants -> scripts package init -> registry -> loader -> planner (partially initialized)`, raising `ImportError: cannot import name 'cascade_names' from partially initialized module`. This cycle was previously latent because `rapyer/init.py` (the only other top-level importer of the planner) always imports `rapyer.base` *before* `rapyer.cascade.planner` in a separate statement, so by the time `loader.py` re-imports planner, it's already fully initialized in `sys.modules`.
- **Fix:** Moved the import of `class_declares_cascade_enabled_sf_ref_edge` to be function-local (lazy) inside `_has_cascade_enabled_sf_ref_edge`, matching the codebase's existing lazy-import convention for breaking real cycles (e.g. `rapyer/types/relational.py`'s lazy `AtomicRedisModel` import, noted in `ARCHITECTURE.md`'s "Circular imports (deliberately worked around)" section).
- **Files modified:** `rapyer/base.py`
- **Verification:** `uv run python -c "import rapyer.base"` succeeds; full `tests/unit/` (818 passed) and `tests/integration/` (1623 passed / 205 skipped) suites pass.
- **Committed in:** `2386b30` (Task 1 commit)

**2. [Rule 1 - Bug] Unit test's plain-expire assertion didn't account for the opted-out model's own SF key**
- **Found during:** Task 1, writing `test_set_ref_opt_out_refresh_ttl_still_uses_plain_expire`.
- **Issue:** The plan's `<behavior>` states the opt-out case "still calls `pipe.expire` (not `run_fcall`)" without specifying call count. A naive `assert_called_once_with(parent.key, ttl)` fails because `CascadeSetRefOptOut.refs` is itself a special field, so `refresh_ttl`'s native-EXPIRE fast path iterates `self.all_keys` (main key + the `refs` SF key), calling `pipe.expire` twice, not once.
- **Fix:** Asserted the full ordered list of `pipe.expire` calls against `parent.all_keys` instead of a single hardcoded call.
- **Files modified:** `tests/unit/cascade/test_cascade_sf_only_trigger_gate.py`
- **Verification:** Test passes; assertion is now correct for any model with special fields, not just SF-container-free ones.
- **Committed in:** `2386b30` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 3, 1 Rule 1)
**Impact on plan:** Both fixes were required for this plan's own Task 1 acceptance criteria to pass -- no scope creep beyond making the plan's mandated gate change and its test actually work.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CASF-04/05/06's literal "when a cascade fires on a parent (asave/aset_ttl/refresh_ttl)" wording is now closed for SF-only cascade-enabled parents at the public-API level, not just at the direct-FCALL level (02-01).
- `contains_fk_field()`, `__init_subclass__`, non-SF models, and cascade-disabled SF-of-FK models are all provably unchanged.
- fakeredis behavior is unaffected (D-01 preserved): `Meta.is_fake_redis or not self._contains_foreign_key()` short-circuits on `is_fake_redis` via Python's `or`, so the new gate is never even evaluated on fakeredis.
- No blockers for subsequent phase work.

---
*Phase: 02-traverse-sf-held-references-server-side-and-re-arm-children*
*Completed: 2026-07-26*

## Self-Check: PASSED

- FOUND: tests/unit/cascade/test_cascade_sf_only_trigger_gate.py
- FOUND: tests/integration/foreign_keys/test_cascade_sf_held_ref_public_api.py
- FOUND: commit 2386b30
- FOUND: commit 7e3e32a
