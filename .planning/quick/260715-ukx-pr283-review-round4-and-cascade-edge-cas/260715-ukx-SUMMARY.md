---
phase: quick-260715-ukx
plan: 01
subsystem: database
tags: [redis, lua, cascade, ttl, foreign-key, testing]

requires: []
provides:
  - build_script_texts() pure helper in rapyer/scripts/registry.py, reused to reload only the cascade TTL script's SHA in noscript-recovery tests
  - CascadeDictCollectionRoot fixture proving dict[K, Reference] cascade parity with list[Reference[T]]
  - CascadeBlanketLeaf.onward fixture + test proving nested-submodel depth-budget truncation actually stops traversal
  - apply.lua WRONGTYPE/corrupt-target hardening (redis.pcall + pcall(cjson.decode))
affects: [cascade, ttl, foreign-keys]

tech-stack:
  added: []
  patterns:
    - "redis.pcall + pcall(cjson.decode) guard pattern for degrading a Lua script to a dead-end instead of aborting on a corrupt/WRONGTYPE reached key"
    - "real-Redis-only regression test for any JSON.GET WRONGTYPE guard (fakeredis 2.34.1 does not emulate WRONGTYPE)"

key-files:
  created: []
  modified:
    - rapyer/scripts/registry.py
    - rapyer/scripts/lua/cascade/apply.lua
    - tests/models/cascade_types.py
    - tests/unit/cascade/conftest.py
    - tests/integration/foreign_keys/conftest.py
    - tests/unit/cascade/test_cascade_plan_table.py
    - tests/unit/cascade/test_cascade_apply_lua.py
    - tests/integration/foreign_keys/test_cascade_ttl_apply.py
    - tests/integration/pipeline/test_pipeline_noscript_recovery.py

key-decisions:
  - "Extracted build_script_texts() as a pure, behavior-preserving refactor so noscript-recovery tests can reload only the cascade script's SHA after SCRIPT FLUSH, closing the gap where those tests were accidentally also testing cascade-script recovery (which the cascade path doesn't self-heal)"
  - "Added CascadeBlanketLeaf.onward (self-referencing blanket edge) rather than a new model, keeping the depth-budget-truncation test additive/inert for every pre-existing fixture use"
  - "WRONGTYPE regression coverage lives exclusively in tests/integration/foreign_keys/ against real_redis_client; no fakeredis equivalent was added since fakeredis's JSON.GET does not emulate WRONGTYPE (documented in CONCERNS.md)"

requirements-completed: []

duration: ~35min
completed: 2026-07-15
---

# Quick Task 260715-ukx: PR #283 Review Round 4 + Cascade Edge Cases Summary

**Closed 4 PR #283 review-round-4 gaps: noscript-recovery tests no longer risk flushing the cascade TTL script itself, dict[K, Reference] cascade now has explicit test coverage, nested-submodel depth-budget truncation is proven (not just non-consumption), and apply.lua's read_reference_paths degrades gracefully instead of aborting the whole EVALSHA on a corrupt/WRONGTYPE reached target.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 4/4 completed
- **Files modified:** 9

## Accomplishments
- `build_script_texts(is_fakeredis=False) -> dict[str, str]` extracted from `register_scripts` (behavior-preserving); noscript-recovery tests now flush all scripts then reload only the cascade TTL script's SHA via `_flush_all_but_cascade`, so the cascade script is never itself the one under NOSCRIPT test
- `CascadeDictCollectionRoot` fixture + plan-table test + real-Redis integration test prove `dict[str, Reference[T]]` cascades identically to `list[Reference[T]]`
- `CascadeBlanketLeaf.onward` (self-referencing blanket edge) + new test prove a node reached only past a holder's exhausted depth budget is genuinely never queued for refresh (TTL stays -1/-2), while every in-budget node on the same path still refreshes
- `apply.lua::read_reference_paths` now wraps `JSON.GET` in `redis.pcall` and `cjson.decode` in `pcall`, degrading to an empty `values_by_path` on a WRONGTYPE error or malformed-JSON decode failure instead of raising and aborting the entire cascade EVALSHA

## Task Commits

Each task was committed atomically:

1. **Task 1: Flush-all-but-cascade in noscript-recovery tests** - `7291357` (test)
2. **Task 2: Cover dict[K, Reference] FK-collection cascade** - `509a1b8` (test)
3. **Task 3: Prove nested-submodel depth-budget truncation** - `24385ae` (test)
4. **Task 4: Skip a corrupt/WRONGTYPE reached target instead of aborting** - `a6833fd` (fix)

## Files Created/Modified
- `rapyer/scripts/registry.py` - Extracted `build_script_texts()` pure helper; `register_scripts` now delegates to it before the SHA-storage loop
- `rapyer/scripts/lua/cascade/apply.lua` - `read_reference_paths` uses `redis.pcall`/`pcall(cjson.decode)` guards to degrade gracefully on WRONGTYPE/corrupt data instead of aborting
- `tests/models/cascade_types.py` - Added `CascadeDictCollectionRoot`; extended `CascadeBlanketLeaf` with a self-referencing `onward` field
- `tests/unit/cascade/conftest.py`, `tests/integration/foreign_keys/conftest.py` - Registered `CascadeDictCollectionRoot` in both cascade model lists
- `tests/unit/cascade/test_cascade_plan_table.py` - New test proving one collection-marked edge for `dict[K, Reference]`
- `tests/unit/cascade/test_cascade_apply_lua.py` - New test proving depth-budget truncation past a holder's exhausted budget
- `tests/integration/foreign_keys/test_cascade_ttl_apply.py` - New dict-value-FK-refresh test; new WRONGTYPE regression test (RED before Task 4's fix, GREEN after)
- `tests/integration/pipeline/test_pipeline_noscript_recovery.py` - `_flush_all_but_cascade` helper replaces raw `SCRIPT FLUSH` calls in all 3 tests

## Decisions Made
None beyond what's captured in `key-decisions` above - followed plan as specified.

## Deviations from Plan

**1. [Minor - test import] `CascadeChainNode` import omitted from Task 4's integration test**

The plan's action text said to import `CascadeChainNode, CascadeChainRoot` alongside the existing imports in `test_cascade_ttl_apply.py`. The new test only ever references `CascadeChainNode` as a plain string literal (`"CascadeChainNode:corrupt"`, matching a Redis key shape) — it never uses the class symbol itself. Importing it unused would fail `ruff check` (F401, the project's enabled unused-import rule) and get silently stripped by the repo's ruff-fix hook. Only `CascadeChainRoot` (used to construct the root model) was kept as an import.
- **Files modified:** `tests/integration/foreign_keys/test_cascade_ttl_apply.py`
- **Commit:** `a6833fd`

**2. [Rule 3 - blocking test-order note] WRONGTYPE regression trips during `asave()`, not only the explicit `_apply_cascade` call**

Confirming Task 4's RED state showed the pre-fix `ResponseError` actually surfaces during the test's Arrange step (`CascadeChainRoot(...).asave()`'s own auto-cascade-TTL-refresh), not only at the explicit `_apply_cascade` Act call the plan described — because `asave()` on a cascade-enabled model already runs the cascade script once via its outermost-action TTL-refresh wrapper. This is the same underlying bug (a WRONGTYPE reached target aborts the cascade Lua script) manifesting one call earlier than the plan's narrative implied. No code change was needed beyond the planned Lua fix; the test's Act/Assert against `_apply_cascade` and the final TTL assertions are unaffected and still confirm both RED (pre-fix) and GREEN (post-fix) correctly.
- **Found during:** Task 4 (confirming the RED state before applying the Lua fix)
- **Files modified:** none (observation only)
- **Verification:** Ran the test standalone before and after the Lua edit — RED (`ResponseError`) before, GREEN (1 passed) after
- **Committed in:** `a6833fd` (part of Task 4's commit)

---

**Total deviations:** 2 (1 minor import omission required by ruff's unused-import rule, 1 observational note about where the RED failure surfaces)
**Impact on plan:** No scope creep; both deviations are cosmetic/observational and don't change the fix, its coverage, or the plan's stated done-criteria.

## Issues Encountered
None - the repo's PostToolUse ruff-fix hook stripped unused imports mid-edit several times (a known project behavior per user memory: "add an import and its usage in the same Edit"); each occurrence was immediately corrected by re-adding the import in the same edit as its usage, with no impact on the final committed state.

## User Setup Required
None - no external service configuration required.

## Verification Summary

- Full suite (`REDIS_DB=0 python -m pytest tests -q -p no:randomly`, real Redis Stack on localhost:6370) ran green after every task: 2422 -> 2424 -> 2425 -> 2426 passed (205 skipped throughout), 0 failures at each checkpoint.
- `black --check --diff` and `ruff check` clean on every touched file after every task.
- Task 4's regression test (`test_cascade_apply_skips_corrupt_wrongtype_reached_target_sanity`) was confirmed RED before the Lua fix (`ResponseError` from a genuine WRONGTYPE on real Redis Stack) and GREEN after (1 passed) — this is the sole regression guard for the fix; no fakeredis equivalent was added since fakeredis 2.34.1's `JSON.GET` does not emulate WRONGTYPE (documented in `.planning/codebase/CONCERNS.md`, gitignored/not committed per plan constraints).
- `git diff` on `rapyer/scripts/registry.py` confirms a pure extraction: `SCRIPT_REGISTRY`, `_inject_sf_dispatch`, `_inject_cascade_plan`, and the SHA-storage loop's semantics are all unchanged.
- `git diff` on `rapyer/scripts/lua/cascade/apply.lua` confirms only `read_reference_paths` was touched (the two `pcall`/`redis.pcall` guards); `push_edges`, `queue_refresh`, `plan_refresh_keys`, and the final return shape are untouched.

## Next Phase Readiness
No blockers. This closes out the cascade-ttl PR #283 review-round-4 edge cases; the milestone's cross-AI review can proceed.

---
*Task: quick-260715-ukx*
*Completed: 2026-07-15*

## Self-Check: PASSED

- All 4 commit hashes (`7291357`, `509a1b8`, `24385ae`, `a6833fd`) found in `git log`.
- All key files (`rapyer/scripts/registry.py`, `rapyer/scripts/lua/cascade/apply.lua`, `tests/models/cascade_types.py`, `tests/integration/foreign_keys/test_cascade_ttl_apply.py`) exist on disk.
- `build_script_texts` confirmed present in `rapyer/scripts/registry.py`; `redis.pcall` guard confirmed present in `apply.lua`.
