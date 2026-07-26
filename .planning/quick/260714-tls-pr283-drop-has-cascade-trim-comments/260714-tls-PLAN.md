---
phase: quick-260714-tls
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - rapyer/base.py
  - rapyer/init.py
  - tests/unit/cascade/test_refresh_ttl_cascade_branch.py
  - tests/unit/cascade/test_cascade_action_boundary.py
  - tests/integration/foreign_keys/test_cascade_concurrent_mutation.py
  - tests/integration/foreign_keys/test_cascade_action_boundary.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "AtomicRedisModel no longer declares a _has_cascade ClassVar, and init_rapyer no longer writes it -- the cascade plan table baked into the registered Lua script at register_scripts time is the sole source of cascade-traversal truth, not a per-class Python flag"
    - "build_cascade_plan(REDIS_MODELS) and validate_cascade_ttl_targets(plan) still run during init_rapyer for fail-fast config validation, unaffected by the _has_cascade removal"
    - "refresh_ttl's and aset_ttl's TTL-cascade comment blocks are trimmed to their essential why, with zero change to any ARGV order, the should_execute=False / manual pipe.execute() pattern, or the CascadeResult return"
    - "Full test suite (unit + integration against real Redis Stack) passes with zero references to _has_cascade remaining anywhere in rapyer/ or tests/"
  artifacts:
    - path: "rapyer/base.py"
      provides: "AtomicRedisModel without a _has_cascade ClassVar; refresh_ttl/aset_ttl with trimmed comment blocks and unchanged logic"
    - path: "rapyer/init.py"
      provides: "init_rapyer still calling build_cascade_plan/validate_cascade_ttl_targets for fail-fast validation, with the _has_cascade-marking loop removed"
  key_links:
    - from: "rapyer/init.py init_rapyer"
      to: "rapyer/cascade/planner.py build_cascade_plan"
      via: "validate_cascade_ttl_targets(build_cascade_plan(REDIS_MODELS)) still called for config validation, independent of _has_cascade"
      pattern: "validate_cascade_ttl_targets\\(build_cascade_plan\\(REDIS_MODELS\\)\\)"
---

<objective>
Resolve PR #283 review round 2: remove the dead `_has_cascade` product state (written in `init.py`/declared in `base.py`, never read by any production code since PR #283 #8 unified `aset_ttl`/`refresh_ttl` to always route through the cascade Lua script), and trim two over-long comment blocks in `rapyer/base.py`'s TTL-cascade path down to their essential why.

Purpose: Close out reviewer feedback with zero behavior change -- the real cascade traversal is driven entirely by the plan table baked into the Lua script at `register_scripts` time, so `_has_cascade` was leftover bookkeeping from the pre-unification branch, and the trimmed comments were pre-unification prose that no longer matches the current single-path implementation.
Output: `rapyer/base.py` and `rapyer/init.py` with `_has_cascade` fully removed; six test files with their `_has_cascade` stashing fixtures/assertions stripped (behavior of the tests themselves unchanged, since they already prove behavior via `run_sha`/TTL assertions, not via the flag); two comment blocks in `rapyer/base.py` trimmed to concise essential-why prose.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md

<interfaces>
Current state being removed (rapyer/base.py:173): `_has_cascade: ClassVar[bool] = False` on `AtomicRedisModel`, alongside `_contain_fk`/`_contain_sf`/etc. -- delete this one line only, leave every sibling ClassVar untouched.

Current state being removed (rapyer/init.py:77-84), inside `init_rapyer`'s existing `try:` block that already computes the plan for validation:
  plan = build_cascade_plan(REDIS_MODELS)
  validate_cascade_ttl_targets(plan)
  # Reuse the plan to mark which classes have outgoing cascade edges.
  for model in REDIS_MODELS:
      model._has_cascade = bool(plan[model.__name__].fks)
KEEP the first two lines (fail-fast config validation, needs no Redis connection) -- since `plan` becomes otherwise-unused after the loop is deleted, inline it as a single expression: `validate_cascade_ttl_targets(build_cascade_plan(REDIS_MODELS))`. The surrounding `finally:` block (refreeze `Meta._meta_locked = True` for every model) is untouched and must still run on both success and failure.

Test fixtures being simplified, all following the identical shape "stash `_has_cascade` via `build_cascade_plan`, yield, restore" on top of an already-real setup fixture:
- tests/unit/cascade/test_refresh_ttl_cascade_branch.py: module-level `_STASH_MODELS` list + autouse `stash_has_cascade` fixture wrapping the whole module, plus two `assert Model._has_cascade is True/False` lines inside the two test bodies.
- tests/unit/cascade/test_cascade_action_boundary.py: `setup_fake_redis_for_action_boundary` fixture takes `setup_fake_redis_for_cascade_apply` as its sole dependency and adds nothing but the `_has_cascade` stash on top of it.
- tests/integration/foreign_keys/test_cascade_action_boundary.py: `setup_real_redis_for_action_boundary` fixture takes `setup_real_redis_for_cascade_apply` as its sole dependency and adds nothing but the `_has_cascade` stash on top of it.
- tests/integration/foreign_keys/test_cascade_concurrent_mutation.py: `setup_real_redis_for_concurrent_mutation` fixture takes `setup_real_redis_for_cascade_apply` as its sole dependency and adds nothing but the `_has_cascade` stash on top of it; the test function requests this fixture explicitly as a parameter (module also carries `pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")` separately).

In all four test files, once the stash is removed, the wrapper fixture becomes a pure pass-through of the base fixture it composed on -- delete the wrapper entirely and point tests directly at the base fixture (`setup_fake_redis_for_cascade_apply` / `setup_real_redis_for_cascade_apply`), rather than leaving an empty pass-through fixture around.

rapyer/base.py comment blocks to trim (text only, logic byte-identical before/after):
- refresh_ttl, immediately above the `scripts_registry.run_sha(...)` call: currently 7 comment lines starting "# Always go through the cascade script, and always cascade (ARGV" through "# pipe.expire returns were."
- aset_ttl, three separate comment spans: (1) the ~10-line block starting "# Always route through the cascade script -- unified for both cascade" through "# alive." plus the blank "#" line, explaining the cascade ARGV semantics; (2) the 2-line "# Check for an outer pipeline BEFORE entering the pipeline context, / # since ensure_pipeline itself pushes a pipeline into context." note -- keep this one, just verify it stays adjacent to `in_outer_pipe = _context_pipe.get() is not None`; (3) the 4-line "# NOTE: bare execute -- this TTL-refresh path does not yet / # self-heal a NOSCRIPT..." block referencing NOSCRIPT-ISSUE.md.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Remove dead _has_cascade product state from production code and its six test call sites</name>
  <files>rapyer/base.py, rapyer/init.py, tests/unit/cascade/test_refresh_ttl_cascade_branch.py, tests/unit/cascade/test_cascade_action_boundary.py, tests/integration/foreign_keys/test_cascade_concurrent_mutation.py, tests/integration/foreign_keys/test_cascade_action_boundary.py</name>
  <action>
    In rapyer/base.py: delete the `_has_cascade: ClassVar[bool] = False` line (~173). No other line in this file references `_has_cascade`.

    In rapyer/init.py: inside `init_rapyer`'s `try:` block, delete the `# Reuse the plan to mark which classes have outgoing cascade edges.` comment and the `for model in REDIS_MODELS: model._has_cascade = ...` loop that follows `validate_cascade_ttl_targets(plan)`. Since `plan` is now unused after that point, collapse the two preceding lines into one: `validate_cascade_ttl_targets(build_cascade_plan(REDIS_MODELS))`, keeping the "Fail fast on a mis-configured cascade graph..." comment above it unchanged. Do not touch the `finally:` block that refreezes `Meta._meta_locked`.

    In tests/unit/cascade/test_refresh_ttl_cascade_branch.py: delete the `_STASH_MODELS` list, its preceding multi-line comment (references `_has_cascade` and the stashing rationale), and the `stash_has_cascade` autouse fixture. Remove the two `assert Model._has_cascade is True/False` lines from inside the two test bodies (`test_refresh_ttl_cascade_enabled_model_calls_run_sha_not_expire` and `test_refresh_ttl_non_cascade_model_also_calls_run_sha`) -- each test's remaining `run_sha`/`expire.assert_not_called()` assertions already fully prove the behavior. Remove the now-unused `build_cascade_plan` import if nothing else in the file uses it.

    In tests/unit/cascade/test_cascade_action_boundary.py: in the `setup_fake_redis_for_action_boundary` fixture, remove the `_has_cascade` stash/restore logic and its docstring's reference to it. Since the fixture becomes a pure pass-through of `setup_fake_redis_for_cascade_apply` with nothing added, delete the fixture entirely and change the module-level `pytestmark = pytest.mark.usefixtures("setup_fake_redis_for_action_boundary")` to reference `"setup_fake_redis_for_cascade_apply"` directly. Remove the now-unused `build_cascade_plan` import and the `CASCADE_PLANNER_MODELS` import from `tests.unit.cascade.conftest` if nothing else in the file uses them. Fix the comment at ~line 118 ("A healthy _has_cascade=True parent -> child...") to describe the fixture state without referencing the removed attribute (e.g. "A healthy parent -> child pair...").

    In tests/integration/foreign_keys/test_cascade_action_boundary.py: same pattern as the unit-test file above -- delete the `_has_cascade` stash/restore logic and docstring reference inside `setup_real_redis_for_action_boundary`; since it becomes a pure pass-through of `setup_real_redis_for_cascade_apply`, delete the fixture entirely and point the module-level `pytestmark` at `"setup_real_redis_for_cascade_apply"` directly. Remove the now-unused `build_cascade_plan` import and `CASCADE_INTEGRATION_MODELS` import if nothing else in the file uses them.

    In tests/integration/foreign_keys/test_cascade_concurrent_mutation.py: same pattern -- delete the `_has_cascade` stash/restore logic and docstring reference inside `setup_real_redis_for_concurrent_mutation`; since it becomes a pure pass-through of `setup_real_redis_for_cascade_apply` (already applied module-wide via the existing `pytestmark`), delete the fixture entirely and remove its now-unneeded parameter from the one test function that requests it (`test_cascade_races_concurrent_fk_reassignment_reflects_one_consistent_snapshot_sanity`). Remove the now-unused `build_cascade_plan` import and `CASCADE_INTEGRATION_MODELS` import if nothing else in the file uses them.

    After all edits, grep the whole repo to confirm zero remaining `_has_cascade` references in rapyer/ and tests/ (a match on `test_aset_ttl_cascade_flag.py`'s `test_aset_ttl_signature_has_cascade_kwarg_defaulting_false` test name is expected and fine -- it names the `cascade` kwarg, not the `_has_cascade` attribute, and is out of scope).
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && ! grep -rn "_has_cascade" rapyer/ tests/ && REDIS_DB=0 python -m pytest tests -q -p no:randomly && black --check --diff rapyer/base.py rapyer/init.py tests/unit/cascade/test_refresh_ttl_cascade_branch.py tests/unit/cascade/test_cascade_action_boundary.py tests/integration/foreign_keys/test_cascade_concurrent_mutation.py tests/integration/foreign_keys/test_cascade_action_boundary.py && ruff check rapyer/base.py rapyer/init.py tests/unit/cascade/test_refresh_ttl_cascade_branch.py tests/unit/cascade/test_cascade_action_boundary.py tests/integration/foreign_keys/test_cascade_concurrent_mutation.py tests/integration/foreign_keys/test_cascade_action_boundary.py</automated>
  </verify>
  <done>Zero repo-wide references to _has_cascade remain (outside the unrelated cascade-kwarg test name); build_cascade_plan/validate_cascade_ttl_targets still run in init_rapyer for fail-fast validation; full suite (REDIS_DB=0 python -m pytest tests -q -p no:randomly against real Redis Stack on localhost:6370) passes with 0 failures; black and ruff clean on all six touched files.</done>
</task>

<task type="auto">
  <name>Task 2: Trim over-long TTL-cascade comment blocks in rapyer/base.py (comment text only)</name>
  <files>rapyer/base.py</files>
  <action>
    In `refresh_ttl`, replace the 7-line comment block immediately above `scripts_registry.run_sha(...)` (currently spanning "Always go through the cascade script, and always cascade..." through "...pipe.expire returns were.") with at most 2 lines capturing only: refresh_ttl always routes through the cascade script with cascade=1 so the whole reachable subtree is re-armed on every action, and with no outgoing edges it just re-arms this model's own keys.

    In `aset_ttl`, replace the ~10-line comment block explaining the cascade ARGV semantics (from "Always route through the cascade script -- unified for both cascade" through "...Pass a positive ttl to keep the whole subtree alive." plus the blank "#" separator line) with one short line: aset_ttl always routes through the cascade script, and `cascade` is a per-call ARGV (0 = root's own keys only, 1 = walk the FK graph).

    Keep the existing 2-line note "Check for an outer pipeline BEFORE entering the pipeline context, since ensure_pipeline itself pushes a pipeline into context." exactly where it is, immediately above `in_outer_pipe = _context_pipe.get() is not None` -- do not delete or reword it.

    Collapse the 4-line NOSCRIPT follow-up comment (starting "NOTE: bare execute -- this TTL-refresh path does not yet self-heal a NOSCRIPT...") into one line that still references the tracked follow-up in NOSCRIPT-ISSUE.md.

    Do not change any code: no ARGV order, no `should_execute=False` / manual `pipe.execute()` pattern, no CascadeResult construction, no control flow. This task touches comment text only.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && git diff --stat rapyer/base.py | grep -q "base.py" && REDIS_DB=0 python -m pytest tests -q -p no:randomly && black --check --diff rapyer/base.py && ruff check rapyer/base.py</automated>
  </verify>
  <done>refresh_ttl's and aset_ttl's cascade comment blocks are trimmed to their essential why (refresh_ttl: <=2 lines; aset_ttl cascade-ARGV explanation: 1 line; NOSCRIPT note: 1 line; outer-pipeline note: unchanged), with zero logic/behavior change; full suite still passes; black and ruff clean on rapyer/base.py.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| None crossed | Pure internal cleanup: removes a dead class-level flag never read by production code and trims comment prose. No new input, no new code path, no external data crosses any boundary. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | Repudiation (silent behavior drift) | rapyer/base.py, rapyer/init.py, six test files | accept | `_has_cascade` is proven dead (written, never read) by grep before this plan was authored; removal cannot change runtime behavior. Full suite run against real Redis Stack after each task proves this empirically, not just by inspection. |
| T-quick-02 | Tampering (comment/code divergence) | rapyer/base.py refresh_ttl/aset_ttl | mitigate | Task 2 is scoped to comment text only with an explicit "no logic change" constraint; `git diff` on rapyer/base.py after Task 2 must show only comment-line changes, verified by full suite staying green. |

No npm/pip/cargo package installs are introduced by this plan; the package-legitimacy gate does not apply.
</threat_model>

<verification>
1. `grep -rn "_has_cascade" rapyer/ tests/` returns zero matches (aside from the unrelated `test_aset_ttl_signature_has_cascade_kwarg_defaulting_false` test name).
2. `REDIS_DB=0 python -m pytest tests -q -p no:randomly` passes with 0 failures after each task.
3. `black --check --diff` and `ruff check` clean on all touched files.
4. `git diff rapyer/base.py` after Task 2 shows only comment-line changes (no code/logic lines touched).
</verification>

<success_criteria>
- `_has_cascade` ClassVar declaration removed from `AtomicRedisModel`; the marking loop removed from `init_rapyer`; `build_cascade_plan`/`validate_cascade_ttl_targets` still run for fail-fast config validation.
- All six test files' `_has_cascade` stashing fixtures/assertions removed; pure pass-through wrapper fixtures deleted in favor of the base fixture they wrapped.
- `refresh_ttl`'s and `aset_ttl`'s TTL-cascade comment blocks trimmed to essential why, with zero logic change.
- Full suite (`REDIS_DB=0 python -m pytest tests -q -p no:randomly`) green; black/ruff clean on every touched file.
- Two commits: `refactor(cascade): drop dead _has_cascade state (PR #283 review)` and `docs(cascade): trim verbose TTL-path comments in base.py (PR #283 review)`.
</success_criteria>

<output>
Create `.planning/quick/260714-tls-pr283-drop-has-cascade-trim-comments/260714-tls-SUMMARY.md` when done
</output>
