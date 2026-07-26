---
phase: quick-260715-taa
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/unit/cascade/test_aset_ttl_cascade_flag.py
  - tests/unit/cascade/test_cascade_action_boundary.py
  - tests/unit/cascade/test_cascade_apply_lua.py
  - tests/unit/cascade/test_cascade_apply_lua_syntax.py
  - tests/unit/cascade/test_cascade_classification.py
  - tests/unit/cascade/test_cascade_plan_injection.py
  - tests/unit/cascade/test_cascade_plan_table.py
  - tests/unit/cascade/test_cascade_ttl_config.py
  - tests/unit/cascade/test_cascade_ttl_required_validation.py
  - tests/unit/cascade/test_extract_annotation.py
  - tests/unit/cascade/test_meta_ttl_freeze.py
  - tests/unit/cascade/test_refresh_ttl_cascade_branch.py
  - tests/integration/foreign_keys/test_cascade_concurrent_mutation.py
  - tests/integration/foreign_keys/test_cascade_graph_shapes.py
  - tests/integration/foreign_keys/test_cascade_ttl_apply.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Every non-trivial test in the 15 touched cascade test files has bare `# Arrange` / `# Act` / `# Assert` label lines on their own comment lines, with any explanatory prose on the following comment line(s) -- no test in these files still uses a combined label (`# Act / Assert`, `# Act & Assert`, `# Arrange & Act`, `# Arrange / Act`)"
    - "Zero test logic, assertions, fixtures, imports, or behavior changed -- every edit is comment-line insertion, deletion, or splitting only"
    - "Full suite (`REDIS_DB=0 python -m pytest tests -q -p no:randomly` against real Redis Stack on localhost:6370) passes with 0 failures after each task"
    - "black --check and ruff check remain clean on every touched file"
  artifacts:
    - path: "tests/unit/cascade/test_aset_ttl_cascade_flag.py"
      provides: "All 7 tests carry Arrange/Act/Assert (or Act/Assert for the one trivial signature test) as bare label lines"
      contains: "# Arrange"
    - path: "tests/integration/foreign_keys/test_cascade_graph_shapes.py"
      provides: "All 5 tests carry an added `# Arrange` label above their existing Act/Assert-labeled setup, docstrings preserved verbatim"
      contains: "# Arrange"
  key_links:
    - from: "tests/unit/cascade/*.py (11 files)"
      to: "grep -rn 'Act /\\|Act &\\|Arrange &\\|Arrange /' tests/unit/cascade/"
      via: "combined-label grep must return zero matches after Task 1"
      pattern: "Act /|Act &|Arrange &|Arrange /"
    - from: "tests/integration/foreign_keys/*.py (3 files)"
      to: "grep -rn 'Act /\\|Act &\\|Arrange &\\|Arrange /' tests/integration/foreign_keys/"
      via: "combined-label grep must return zero matches after Task 2"
      pattern: "Act /|Act &|Arrange &|Arrange /"
---

<objective>
Add Arrange/Act/Assert (AAA) section-marker comments to every cascade test that currently lacks them or uses a combined label, matching the already-compliant style in `tests/unit/cascade/test_cascade_action_boundary.py` and `tests/integration/foreign_keys/test_cascade_action_boundary.py`. Comment-only change -- PR #283 review cleanup.

Purpose: Make the reviewer-requested AAA structure consistent across the whole cascade test suite so every test's setup/action/verification phases are visually scannable, with zero risk to the TTL-cascade behavior these tests protect (no logic, assertion, fixture, or import changes).
Output: 15 test files (12 unit, 3 integration) with bare `# Arrange` / `# Act` / `# Assert` label lines added or split from combined labels; full suite still green; black/ruff clean.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md

<interfaces>
Established AAA convention (from the already-compliant tests in `tests/unit/cascade/test_cascade_action_boundary.py`, e.g. `test_aset_ttl_cascade_true_healthy_splits_parent_and_child_ttl_and_reports_no_dangling`):
- `# Arrange`, `# Act`, `# Assert` are each a BARE label on their OWN comment line -- never combined with prose or with each other on the same line.
- Explanatory "why" prose goes on the comment line(s) immediately BELOW the label, never on the same line as the label.
- A single test may have more than one `# Assert` block (or `# Act` / `# Assert` pair) when it verifies multiple independent things in sequence -- this is an established, accepted pattern in this suite, not something to collapse into one block.
- Existing prose comments inside a test body are PRESERVED, just re-homed underneath the correct label (never deleted for being "redundant" with the label).
- Docstrings (`"""..."""`) at the top of a test body are left untouched; labels/prose are ADDED after them, not merged into them.

Resolution rules for lines where Act and Assert (or Arrange and Act) are the SAME physical line of code (common in this suite's one-line `assert fn(...) == expected` tests and `with pytest.raises(...):` blocks) -- apply consistently, do not reorder code to force a clean split:
- Combined label above a single `assert <call> == <expected>` line where the call IS the assertion (no separate act step exists): stack the two bare labels back-to-back directly above that one line, e.g.:
  `    # Act`
  `    # Assert`
  `    assert _field_cascade_spec(CascadeBookDirect, "author") == CascadeTTL(enabled=False)`
- `with pytest.raises(...): <call under test>` followed by a separate trailing `assert exc_info.value.<attr> == ...` line: label the `with pytest.raises(...):` block as `# Act` (it executes the code under test and captures the expected exception) and the trailing attribute-check line as `# Assert` (verifies the caught exception) -- these are naturally two separate lines, so split them for real, do not stack.
- `with pytest.raises(...): <mutation>` immediately followed by another assert line already on its own line (e.g. `test_frozen_redis_config_ttl_assignment_raises_and_leaves_ttl_unchanged_sanity` in `test_meta_ttl_freeze.py`): same as above -- `# Act` above the `with` block, `# Assert` above the trailing assert line.
- A test with NO assert statement at all (import-only sanity check, e.g. `test_build_cascade_plan_is_importable`, `test_cascade_target_ttl_missing_error_is_importable_from_rapyer_errors`): genuinely trivial, leave UNLABELED -- do not invent Arrange/Act/Assert structure per the trivial-test carve-out.
- A test with a call but no assert at all (a "must not raise" test, e.g. `test_does_not_raise_when_target_ttl_is_set`, `test_does_not_raise_for_a_class_never_reached_as_a_target_even_with_no_ttl`): label only what exists -- `# Arrange` (if there is a distinct setup step) then `# Act` above the call; no `# Assert` label since there is no assertion line to label.
- A test whose entire body is verification of already-configured module-level fixtures/globals with no function call under test (e.g. `test_every_cascade_fixture_has_the_shared_fixture_ttl_sanity`, `test_flagged_invocation_root_only_fixtures_have_ttl_sanity` in `test_cascade_plan_table.py`): label the whole body `# Assert` only (no Arrange/Act), preserving existing prose underneath.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add AAA markers to unit cascade tests</name>
  <files>tests/unit/cascade/test_aset_ttl_cascade_flag.py, tests/unit/cascade/test_cascade_action_boundary.py, tests/unit/cascade/test_cascade_apply_lua.py, tests/unit/cascade/test_cascade_apply_lua_syntax.py, tests/unit/cascade/test_cascade_classification.py, tests/unit/cascade/test_cascade_plan_injection.py, tests/unit/cascade/test_cascade_plan_table.py, tests/unit/cascade/test_cascade_ttl_config.py, tests/unit/cascade/test_cascade_ttl_required_validation.py, tests/unit/cascade/test_extract_annotation.py, tests/unit/cascade/test_meta_ttl_freeze.py, tests/unit/cascade/test_refresh_ttl_cascade_branch.py</files>
  <action>
Apply the interfaces resolution rules above to every test listed below. Do not touch `test_init_rapyer_cascade_ttl.py` or any test not named here (they are already compliant or out of scope).

**test_aset_ttl_cascade_flag.py** (all 7 tests, currently no markers): `test_aset_ttl_signature_has_cascade_kwarg_defaulting_false` -- Act above `sig = inspect.signature(...)`, Assert above the two `assert "cascade" in ...` / `assert sig.parameters[...].default is False` lines. The other 6 tests (`test_aset_ttl_default_cascade_false_runs_the_script_with_cascade_argv_zero`, `test_aset_ttl_cascade_true_runs_the_script_with_cascade_argv_one`, `test_aset_ttl_cascade_standalone_owns_execution_and_returns_cascade_result`, `test_aset_ttl_cascade_standalone_awaits_pipe_execute_directly`, `test_aset_ttl_cascade_inside_outer_pipeline_returns_none_without_executing`, `test_aset_ttl_cascade_false_on_fk_edged_model_refreshes_only_root`) each follow: Arrange = model/mock_pipe/fake_ensure_pipeline construction through the `with (...)` context entry (keep any existing inline "why" comment as Arrange prose), Act = the single `result = await root.aset_ttl(...)` call, Assert = the `mock_run_sha.assert_called_once_with(...)` block plus any trailing `assert result == ...` / `mock_pipe.execute.assert_*` lines.

**test_cascade_action_boundary.py** (only `test_asave_on_non_cascade_model_refreshes_ttl_via_the_cascade_script`): keep the existing "refresh_ttl always routes through the cascade script now..." prose comment where it is, then Act above the `with patch("rapyer.base.scripts_registry.run_sha") as mock_run_sha: await CascadeBookPlain(...).asave()` block, Assert above the two trailing `assert mock_run_sha....` lines.

**test_cascade_apply_lua.py** (add ONLY the missing `# Arrange` label to 3 tests that already have Act/Assert): `test_depth0_shallow_root_extends_via_explicit_override_matches_hand_derived_expected_set`, `test_independent_sibling_depth_budgets_match_hand_derived_expected_set`, `test_nested_submodel_zero_hop_does_not_consume_depth_budget` -- for each, insert a bare `# Arrange` line immediately before the existing multi-line explanatory prose comment that precedes the setup code (the prose stays below the new label, unchanged). Do not touch Act/Assert in these 3, and do not touch any other test in this file.

**test_cascade_apply_lua_syntax.py** (the 1 test, `test_cascade_apply_lua_is_syntactically_valid`, no markers): this test performs two act+verify steps back to back -- label `# Act` above `text = _load_template("cascade", "apply")` and `# Assert` above `assert "--[[CASCADE_PLAN_TABLE]]" in text` (verifies the loaded template contains the injection placeholder), then a second `# Act` above `sha = await fake_redis_client.script_load(text)` and a second `# Assert` above the trailing `assert isinstance(sha, str)` / `assert sha` pair (verifies the script compiled). Two Act/Assert pairs in one body is established elsewhere in this suite (see the multi-Assert tests in `test_cascade_apply_lua.py`).

**test_cascade_classification.py** (all 7 tests, split combined `# Act / Assert`): every test in this file is a single `assert _field_cascade_spec(...) == ...` (or `assert Model._relational_field_names == ...`) line where the call IS the assertion -- for each, replace the one-line `# Act / Assert` comment with two bare stacked lines, `# Act` then `# Assert`, directly above the unchanged assert line. Applies to `test_direct_fk_field_records_exact_cascade_ttl_instance`, `test_collection_fk_field_records_cascade_ttl_on_the_collection_field`, `test_nested_submodel_records_marker_on_the_nested_class_not_the_outer_one`, `test_plain_fk_field_without_cascade_ttl_has_empty_cascade_ttl_fields`, `test_plain_fk_field_classification_is_unaffected`, `test_cascade_author_leaf_model_has_no_cascade_ttl_fields`, `test_existing_fk_book_classification_remains_byte_identical`.

**test_cascade_plan_injection.py** (all 7 tests, no markers): `test_cascade_ttl_apply_script_name_is_registered_constant` and `test_cascade_registry_entry_present` -- each a single `assert <expr>` line, stack `# Act` / `# Assert` above it (same pattern as test_cascade_classification.py). `test_inject_cascade_plan_is_noop_when_placeholder_absent` -- Arrange above `template = ...` / `plan = {...}`, stacked `# Act` / `# Assert` above the single `assert _inject_cascade_plan(template, plan) == template` line. `test_inject_cascade_plan_escapes_single_quote_in_class_name` -- Arrange above `plan = {"A's": ...}`, Act above `injected = _inject_cascade_plan(...)`, Assert above `assert "--[[CASCADE_PLAN_TABLE]]" not in injected` (keep the existing "A naive, unescaped f-string..." prose beneath), then a second Act above `script = f'...'` / `sha = await fake_redis_client.script_load(script)`, second Assert above the trailing `assert isinstance(sha, str)` / `assert sha`. `test_inject_cascade_plan_serializes_bool_int_and_omits_absent_depth` -- Arrange above `plan = {...}`, Act above `injected = _inject_cascade_plan(...)`, Assert above the remaining asserts (keep the existing "A bare depth substring..." prose under Assert). `test_register_scripts_registers_cascade_ttl_apply` -- Act above `await register_scripts(...)`, Assert above the trailing assert. `test_register_scripts_leaves_sf_only_scripts_unaffected` -- Arrange above the local `from rapyer.scripts.constants import ATOMIC_GET_OR_CREATE_SCRIPT_NAME` line, Act above `await register_scripts(...)`, Assert above the trailing assert.

**test_cascade_plan_table.py** (all 13 tests, no markers): `test_build_cascade_plan_is_importable` has no assert statement -- leave UNLABELED per the trivial-test carve-out. For the 10 tests whose entire body is `plan = build_cascade_plan([...])` followed immediately by assertion(s) with no distinct setup step (`test_shape1_disabled_field_produces_no_edge`, `test_shape1_blanket_enabled_produces_one_edge_with_global_depth`, `test_shape2_collection_of_fk_produces_exactly_one_edge_marked_collection`, `test_shape3_nested_submodel_edge_lands_on_holder_and_hides_nested_class`, `test_depth_key_absent_when_unbounded_never_present_as_none`, `test_ttl_is_read_verbatim_from_meta`, `test_special_suffixes_direct_special_field`, `test_special_suffixes_nested_inside_contain_sf_submodel`, `test_build_cascade_plan_over_redis_models_never_uses_none_as_unbounded_signal`, `test_every_model_gets_exactly_one_entry_even_a_plain_leaf`): label `# Act` above the `plan = build_cascade_plan(...)` call, `# Assert` above the assertion(s) that follow, preserving any existing explanatory prose (e.g. the "CascadeAuthor now carries..." comment in `test_every_model_gets_exactly_one_entry_even_a_plain_leaf`, the "CascadeProfile still gets..." comment in the shape3 test) beneath the Assert label. For the 2 tests that verify already-configured module-level fixtures with no `build_cascade_plan` call in the body (`test_every_cascade_fixture_has_the_shared_fixture_ttl_sanity`, `test_flagged_invocation_root_only_fixtures_have_ttl_sanity`): label the whole body `# Assert` only, keeping the existing prose beneath it.

**test_cascade_ttl_config.py** (5 named tests, split combined `# Act & Assert`): `test_cascade_ttl_defaults_match_explicit_construction_sanity` and `test_ttl_cascade_mode_has_extend_member_sanity` -- single `assert <expr>` line, stack `# Act` / `# Assert` above it. `test_cascade_ttl_is_frozen_dataclass_sanity` -- keep existing `# Arrange` above `cascade_ttl = CascadeTTL()`, then stack `# Act` / `# Assert` above the `assert dataclasses.is_dataclass(cascade_ttl)` + `with pytest.raises(dataclasses.FrozenInstanceError): cascade_ttl.enabled = False` pair (both lines together are the single verification unit here -- no separate act exists). `test_cascade_ttl_negative_depth_raises_sanity` -- stack `# Act` / `# Assert` above the `with pytest.raises(InvalidCascadeDepthError): CascadeTTL(depth=depth)` block (no separate Arrange -- `depth` comes from `@pytest.mark.parametrize`). `test_cascade_spec_negative_depth_raises_sanity` -- keep the local `ConcreteCascadeSpec` dataclass definition under a new `# Arrange` label, then stack `# Act` / `# Assert` above the `with pytest.raises(InvalidCascadeDepthError): ConcreteCascadeSpec(depth=-1)` block. Do not touch `test_cascade_ttl_default_values_sanity` or `test_cascade_ttl_valid_depth_does_not_raise_sanity` (already compliant with separate Act/Assert).

**test_cascade_ttl_required_validation.py** (all 7 tests, no markers): `test_cascade_target_ttl_missing_error_is_importable_from_rapyer_errors` has no assert -- leave UNLABELED (trivial carve-out). `test_raises_when_cascade_reachable_target_has_no_ttl`, `test_raises_when_cascade_root_has_edges_but_no_ttl`, `test_raises_rapyer_error_when_edge_target_absent_from_partial_plan`, `test_raises_on_first_violation_deterministically_sorted_by_class_name` -- each follows Arrange (the `plan = _plan(...)` or literal dict construction, keep any existing prose comment beneath), Act (the `with pytest.raises(CascadeTargetTtlMissingError) as exc_info: validate_cascade_ttl_targets(plan)` block), Assert (the trailing `assert exc_info.value.model_name == ...` line, keep the "A sorts before M" comment beneath Assert in the last one). `test_does_not_raise_when_target_ttl_is_set` -- Arrange above `plan = _plan(a_ttl=30, b_ttl=60)` (keep existing prose), Act above `validate_cascade_ttl_targets(plan)` -- no Assert label (no assertion exists; success is "did not raise"). `test_does_not_raise_for_a_class_never_reached_as_a_target_even_with_no_ttl` -- Arrange above `plan = {...}`, Act above `validate_cascade_ttl_targets(plan)` -- no Assert label, same reason.

**test_extract_annotation.py** (only `test_non_annotated_field_returns_none`): replace the combined `# Arrange / Act` comment with two stacked bare lines, `# Arrange` then `# Act`, directly above the unchanged `result = extract_annotation(int, CascadeTTL)` line (no separate arrange variables exist -- args are inline literals, mirroring how the other already-compliant tests in this file use one label per line). Keep the trailing `# Assert` above `assert result is None` as-is.

**test_meta_ttl_freeze.py** (2 named tests): `test_fresh_redis_config_ttl_assignment_never_raises_sanity` -- replace `# Arrange & Act` with two stacked bare lines, `# Arrange` then `# Act`, above `config = RedisConfig(ttl=30)`. `test_frozen_redis_config_ttl_assignment_raises_and_leaves_ttl_unchanged_sanity` -- keep the existing `# Arrange` above `config = RedisConfig(ttl=30)` / `config._meta_locked = True`, then split the combined `# Act & Assert` into a real `# Act` above `with pytest.raises(MetaFrozenError): config.ttl = 60` and a real `# Assert` above the separate trailing `assert config.ttl == 30` line (these are two distinct lines already, so split for real rather than stacking). Do not touch `test_two_sequential_init_rapyer_calls_with_different_ttls_both_succeed_sanity` (already compliant).

**test_refresh_ttl_cascade_branch.py** (both tests, no markers): for `test_refresh_ttl_cascade_enabled_model_calls_run_sha_not_expire` and `test_refresh_ttl_non_cascade_model_also_calls_run_sha` -- Arrange above the model/mock_pipe/`fake_ensure_pipeline` construction (keep the "refresh_ttl always routes through the cascade script..." prose in the second test as Arrange prose), Act above the `with (...): await <model>.refresh_ttl(can_use_pipeline=True)` block, Assert above the trailing `mock_run_sha.assert_called_once_with(...)` / `mock_pipe.expire.assert_not_called()` lines.

After all edits: run `grep -rn "Act /\|Act &\|Arrange &\|Arrange /" tests/unit/cascade/` and confirm zero matches.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && ! grep -rn "Act /\|Act &\|Arrange &\|Arrange /" tests/unit/cascade/ && REDIS_DB=0 python -m pytest tests -q -p no:randomly && black --check --diff tests/unit/cascade/test_aset_ttl_cascade_flag.py tests/unit/cascade/test_cascade_action_boundary.py tests/unit/cascade/test_cascade_apply_lua.py tests/unit/cascade/test_cascade_apply_lua_syntax.py tests/unit/cascade/test_cascade_classification.py tests/unit/cascade/test_cascade_plan_injection.py tests/unit/cascade/test_cascade_plan_table.py tests/unit/cascade/test_cascade_ttl_config.py tests/unit/cascade/test_cascade_ttl_required_validation.py tests/unit/cascade/test_extract_annotation.py tests/unit/cascade/test_meta_ttl_freeze.py tests/unit/cascade/test_refresh_ttl_cascade_branch.py && ruff check tests/unit/cascade/test_aset_ttl_cascade_flag.py tests/unit/cascade/test_cascade_action_boundary.py tests/unit/cascade/test_cascade_apply_lua.py tests/unit/cascade/test_cascade_apply_lua_syntax.py tests/unit/cascade/test_cascade_classification.py tests/unit/cascade/test_cascade_plan_injection.py tests/unit/cascade/test_cascade_plan_table.py tests/unit/cascade/test_cascade_ttl_config.py tests/unit/cascade/test_cascade_ttl_required_validation.py tests/unit/cascade/test_extract_annotation.py tests/unit/cascade/test_meta_ttl_freeze.py tests/unit/cascade/test_refresh_ttl_cascade_branch.py</automated>
  </verify>
  <done>All listed unit tests carry bare Arrange/Act/Assert labels (or the documented trivial/no-assert exceptions); grep for combined-label patterns in tests/unit/cascade/ returns zero matches; full suite passes with 0 failures; black --check and ruff check clean on all 12 touched files.</done>
</task>

<task type="auto">
  <name>Task 2: Add AAA markers to integration cascade tests</name>
  <files>tests/integration/foreign_keys/test_cascade_concurrent_mutation.py, tests/integration/foreign_keys/test_cascade_graph_shapes.py, tests/integration/foreign_keys/test_cascade_ttl_apply.py</files>
  <action>
Apply the same interfaces resolution rules from Task 1. Do not touch `test_cascade_action_boundary.py` in this directory (already compliant).

**test_cascade_concurrent_mutation.py** (the 1 test, `test_cascade_races_concurrent_fk_reassignment_reflects_one_consistent_snapshot_sanity`): keep the existing module/test docstring exactly as-is. Add `# Arrange` above the `child_a = await CascadeSpecialChild()...` through the `for key in (child_a.key, child_b.key, parent.key): await real_redis_client.persist(key)` setup block. Add `# Act` above the `async def _reassign_child_and_save():` helper definition through the `cascade_result, _ = await asyncio.gather(...)` call (the helper definition and the gather-call together are the single concurrent action under test). The `# Assert` label already exists above the trailing assertions -- leave it and the assertions untouched.

**test_cascade_graph_shapes.py** (all 5 tests, add ONLY the missing `# Arrange` label -- Act/Assert already present): `test_multi_level_chain_reaches_expected_prefix_sanity`, `test_cyclic_two_node_cycle_does_not_hang_or_error_sanity`, `test_genuine_single_node_self_loop_does_not_hang_or_error_sanity`, `test_diamond_shared_child_refreshed_exactly_once_via_either_edge_sanity`, `test_shared_child_via_two_independent_roots_refreshed_from_either_root_sanity` -- for each, keep the existing docstring untouched, then insert a bare `# Arrange` line immediately before the model-creation/persist setup code that follows the docstring (before the existing `# Act` label). Do not touch Act or Assert labels or any assertion text.

**test_cascade_ttl_apply.py** (both tests, add ONLY the missing `# Arrange` label -- Act/Assert already present): `test_cascade_apply_refreshes_special_field_child_keys_sanity` and `test_cascade_apply_refreshes_every_collection_of_fk_element_sanity` -- for each, insert a bare `# Arrange` line immediately before the existing explanatory prose comment ("Identical scenario/assertions to the fakeredis version..." / "On REAL Redis, JSON.GET's single-path response...") that precedes the setup code, keeping that prose beneath the new label. Do not touch the module-level trailing NOTE comment (not part of any test body) or Act/Assert labels.

After all edits: run `grep -rn "Act /\|Act &\|Arrange &\|Arrange /" tests/integration/foreign_keys/` and confirm zero matches.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && ! grep -rn "Act /\|Act &\|Arrange &\|Arrange /" tests/integration/foreign_keys/ && REDIS_DB=0 python -m pytest tests -q -p no:randomly && black --check --diff tests/integration/foreign_keys/test_cascade_concurrent_mutation.py tests/integration/foreign_keys/test_cascade_graph_shapes.py tests/integration/foreign_keys/test_cascade_ttl_apply.py && ruff check tests/integration/foreign_keys/test_cascade_concurrent_mutation.py tests/integration/foreign_keys/test_cascade_graph_shapes.py tests/integration/foreign_keys/test_cascade_ttl_apply.py</automated>
  </verify>
  <done>All 7 listed integration tests carry bare Arrange/Act/Assert labels; grep for combined-label patterns in tests/integration/foreign_keys/ returns zero matches; full suite passes with 0 failures; black --check and ruff check clean on all 3 touched files.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| None crossed | Pure test-comment cleanup: no production code, no new input handling, no external data. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-taa-01 | Tampering (comment/code divergence introduced by accidental logic edit) | 15 touched test files | mitigate | Both tasks are scoped to comment-line insertion/splitting only; full suite run after each task proves zero assertion/logic drift, not just visual inspection of the diff. |
| T-quick-taa-02 | Repudiation (silently dropped assertions while "cleaning up" combined labels) | test_cascade_ttl_config.py, test_meta_ttl_freeze.py, test_cascade_classification.py (combined-label splits) | accept | Combined-label splitting only ever adds/splits comment lines above existing code; the resolution rules explicitly forbid reordering or deleting any code line, and the full-suite pass count must match pre-change count. |

No npm/pip/cargo package installs are introduced by this plan; the package-legitimacy gate does not apply.
</threat_model>

<verification>
1. `grep -rn "Act /\|Act &\|Arrange &\|Arrange /" tests/unit/cascade/ tests/integration/foreign_keys/` returns zero matches after both tasks.
2. `REDIS_DB=0 python -m pytest tests -q -p no:randomly` passes with 0 failures after each task (real Redis Stack on localhost:6370).
3. `black --check --diff` and `ruff check` clean on all 15 touched files.
4. `git diff` on every touched file shows only comment-line insertions/modifications -- no assertion, fixture, import, or logic line changed.
</verification>

<success_criteria>
- All unit and integration cascade tests listed in this plan use bare `# Arrange` / `# Act` / `# Assert` label lines with prose (if any) on the line(s) below, matching the style of the already-compliant reference tests.
- No combined labels (`# Act / Assert`, `# Act & Assert`, `# Arrange & Act`, `# Arrange / Act`) remain in `tests/unit/cascade/` or `tests/integration/foreign_keys/`.
- Zero behavior change: full suite (`REDIS_DB=0 python -m pytest tests -q -p no:randomly`) passes with the same test count and 0 failures as before this plan.
- black and ruff clean on all 15 touched files.
- Two commits: `test(cascade): add Arrange/Act/Assert section markers to unit cascade tests (PR #283 review)` and `test(cascade): add Arrange/Act/Assert section markers to integration cascade tests (PR #283 review)`.
</success_criteria>

<output>
Create `.planning/quick/260715-taa-add-aaa-section-markers-to-cascade-tests/260715-taa-SUMMARY.md` when done
</output>
