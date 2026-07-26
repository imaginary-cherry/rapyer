---
phase: quick-260707-v5y
plan: 01
subsystem: testing
tags: [redis, lua, cascade-ttl, pytest, fakeredis, dead-code-removal]

# Dependency graph
requires:
  - phase: quick-260707 (cascade-ttl milestone, plans 01-01 through 02-04)
    provides: CascadePlanner (build_cascade_plan/_static_walk_fk_edges), the registered cascade_ttl_apply Lua script, and the CASCADE_PLANNER_MODELS fixture registry
provides:
  - "rapyer/cascade/planner.py trimmed to its static-only surface (__init__/_next_hop/_resolve_target_cls/_unwrap_nested_model_cls + module-level build_cascade_plan/validate_cascade_ttl_targets/_static_walk_fk_edges/_static_walk_special_suffixes/_unwrap_relational_target)"
  - "Every atraverse-proven behavioral scenario (extend-past-shallower-ancestor, blanket decrement, blanket opt-out, shape-3 nested-submodel budget interaction, diamond dedup, self-reference cycle safety) now proven against the real registered cascade_ttl_apply Lua script instead of a Python-side BFS oracle"
affects: [cascade-ttl milestone follow-on plans that touch rapyer/cascade/planner.py or tests/unit/cascade/]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hand-derived hardcoded expected key sets replace live-oracle (CascadePlanner().atraverse(...)) comparisons in Lua-parity tests — asserting against the production Lua script directly is a stronger proof than a Python-side twin implementation"

key-files:
  created: []
  modified:
    - rapyer/cascade/planner.py
    - tests/unit/cascade/test_cascade_apply_lua.py
  deleted:
    - tests/unit/cascade/test_cascade_planner.py

key-decisions:
  - "Reworded the new ported-tests section comment from '# --- Ported from the deleted CascadePlanner unit tests ---' to '# --- Ported from the deleted client-side-planner unit tests ---' to satisfy both the plan's literal instruction (add an explanatory section header) and its own automated verify command (grep for zero remaining 'CascadePlanner' references) — the two were in direct tension in the plan text; intent (no CascadePlanner import/usage) preserved."

requirements-completed: []

# Metrics
duration: ~35min
completed: 2026-07-07
---

# Quick Task 260707-v5y: Remove Dead Cascade Traversal Summary

**Deleted CascadePlanner's dead-on-production-path async BFS traversal (`atraverse`/`_mget`/`_walk_edges`, ~114 lines) and re-proved all 17 of its Python-oracle test scenarios directly against the registered `cascade_ttl_apply` Lua script, netting -15 tests (815 -> 800) with zero coverage loss.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-07-07T19:04:00Z (approx, per PLAN_START_TIME)
- **Completed:** 2026-07-07T19:39:27Z
- **Tasks:** 2 completed
- **Files modified:** 2 (1 deleted, 1 created-equivalent-via-deletion+edit)

## Accomplishments
- `CascadePlanner.atraverse`/`_mget`/`_walk_edges` deleted from `rapyer/cascade/planner.py` — nothing in the shipped code path called them; `build_cascade_plan` reaches its targets exclusively through the separate, already-correct `_static_walk_fk_edges` static walker.
- `CascadePlanner`'s class docstring and `_static_walk_fk_edges`'s docstring rewritten to describe the reduced, static-only role (no more references to a deleted method).
- `tests/unit/cascade/test_cascade_planner.py` deleted in full (17 tests, all exercising only the deleted `atraverse`).
- The 3 existing Lua/planner parity tests in `test_cascade_apply_lua.py` repointed from a live `CascadePlanner().atraverse(...)` oracle comparison to explicit, hand-derived hardcoded expected key sets (the oracle assertions were redundant — the hardcoded literal was always the ground truth being compared against).
- 2 new tests added to `test_cascade_apply_lua.py`, porting the only two atraverse-only scenarios that had no equivalent coverage elsewhere in that file: blanket opt-out overriding a blanket-enabled global, and nested-submodel (shape-3) zero-hop recursion not consuming the inherited depth budget — both now proven against the real registered Lua script.

## Task Commits

Each task was committed atomically:

1. **Task 1: Delete dead runtime traversal from CascadePlanner and update its docstring** - `c49b0a4` (refactor)
2. **Task 2: Delete test_cascade_planner.py and port its scenarios into the real Lua-apply tests** - `805c30e` (test)

**Plan metadata:** not created (`.planning/` is gitignored in this repo; orchestrator handles the docs commit per repo_note)

## Files Created/Modified
- `rapyer/cascade/planner.py` - Deleted `CascadePlanner._mget`/`atraverse`/`_walk_edges`; rewrote the class docstring and `_static_walk_fk_edges`'s docstring to describe the reduced static-only role. `__init__`/`_next_hop`/`_resolve_target_cls`/`_unwrap_nested_model_cls` and every module-level function (`build_cascade_plan`, `validate_cascade_ttl_targets`, `_static_walk_fk_edges`, `_static_walk_special_suffixes`, `_unwrap_relational_target`) are byte-for-byte unchanged.
- `tests/unit/cascade/test_cascade_apply_lua.py` - Removed the `CascadePlanner` import; repointed 3 parity tests to hardcoded expected sets (dropping the live-oracle comparison + its explanatory comments referencing the deleted planner test); added 2 new tests (`test_blanket_opt_out_field_stops_traversal_despite_blanket_global`, `test_nested_submodel_zero_hop_does_not_consume_depth_budget`) in a new trailing section, plus the 4 new fixture-class imports (`CascadeBlanketLeaf`, `CascadeBlanketNestedHolder`, `CascadeBlanketNestedProfile`, `CascadeBlanketOptOut`, `CascadeNestedDepthRoot`) needed by them.
- `tests/unit/cascade/test_cascade_planner.py` - Deleted (all 17 tests exercised only the now-deleted `CascadePlanner.atraverse`).

## Decisions Made
- The plan's Task 2 instructions asked to title the new test section `# --- Ported from the deleted CascadePlanner unit tests ... ---` while its own automated verify command asserts `! grep -q "CascadePlanner" test_cascade_apply_lua.py`. These two instructions are in direct tension. Resolved by rewording the section comment to `# --- Ported from the deleted client-side-planner unit tests ... ---`, preserving the explanatory intent (this section ports scenarios from the deleted client-side planner's test file) without the literal class name, satisfying both the explicit "zero CascadePlanner references" success criterion and the automated grep check.
- Kept the hand-derived-set comments' reasoning inline exactly as the plan specified for each of the 3 repointed parity tests (extend-past-shallower-ancestor depth arithmetic, depth=0-extends-via-override, and independent sibling depth budgets) rather than only removing the oracle line, per the plan's explicit comment-rewording instructions.

## Deviations from Plan

None requiring a fix — see "Decisions Made" above for the one wording adjustment made to resolve a self-contradiction inside PLAN.md's own instructions (Task 2 comment text vs. its automated verify grep). No production code, test behavior, or coverage was affected by this adjustment; it is a comment-text-only change.

## Issues Encountered
- The repo's PostToolUse Edit hook runs a formatter (black/ruff --fix) after every `Edit` call, which silently stripped newly-added-but-not-yet-used imports (`F401`) before the corresponding test bodies that use them were added. Worked around by adding the new test functions (which reference the fixture classes) before re-adding their imports in a final edit, so the imports were "in use" at format time and survived.

## User Setup Required

None - no external service configuration required.

## Verification Results

All constraint-mandated verification commands were run and passed:

```
$ python -m pytest tests/unit -q
800 passed, 6 warnings in 9.49s
```
(Matches the plan's expected direction exactly: 815 baseline - 17 deleted + 2 ported = 800.)

```
$ python -m pytest tests/integration/foreign_keys/test_cascade_ttl_apply.py -q
3 passed in 0.15s
```
(Run against a real local Redis instance, confirmed reachable via `redis-cli ping` -> `PONG`.)

```
$ black --check rapyer/cascade/planner.py tests/unit/cascade/test_cascade_apply_lua.py
All done! (2 files would be left unchanged.)

$ ruff check rapyer/cascade/planner.py tests/unit/cascade/test_cascade_apply_lua.py
All checks passed!
```

```
$ python -c "import rapyer"
(no output — import succeeded)
```

```
$ grep -rn "atraverse\|CascadePlanner()\._walk_edges\|CascadePlanner()\._mget" rapyer/ tests/
rapyer/scripts/lua/cascade/apply.lua:205:    -- The root frame is UNBOUNDED + not-yet-established, matching atraverse's
```
One residual match: a Lua-comment cross-reference to the (now-deleted) `atraverse` semantics inside `rapyer/scripts/lua/cascade/apply.lua`, a file this task's constraints explicitly forbid modifying ("Do NOT modify rapyer/scripts/lua/cascade/apply.lua"). This is a documentation comment only — no code, test, or import references the deleted methods anywhere in the repo. Left untouched per the out-of-scope constraint; a future plan touching `apply.lua` should update or remove this comment.

## Next Phase Readiness
- `rapyer/cascade/planner.py` and the cascade unit test suite are in a clean, fully-covered state with no dead runtime code.
- The one residual `atraverse` mention in `rapyer/scripts/lua/cascade/apply.lua`'s comment (line 205) is a candidate cleanup for the next plan that touches that file, per this task's own out-of-scope constraint.

---
*Phase: quick-260707-v5y*
*Completed: 2026-07-07*

## Self-Check: PASSED

- FOUND: commit c49b0a4 (Task 1)
- FOUND: commit 805c30e (Task 2)
- FOUND: rapyer/cascade/planner.py
- FOUND: tests/unit/cascade/test_cascade_apply_lua.py
- CONFIRMED DELETED: tests/unit/cascade/test_cascade_planner.py
- FOUND: .planning/quick/260707-v5y-remove-dead-cascade-traversal/260707-v5y-SUMMARY.md
