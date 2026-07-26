---
phase: quick-260720-odi
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - rapyer/context.py
  - rapyer/base.py
  - rapyer/scripts/registry.py
  - rapyer/errors/cascade.py
  - rapyer/errors/__init__.py
  - rapyer/config.py
  - tests/integration/foreign_keys/test_cascade_self_heal.py
autonomous: true
requirements: [REVERT-284]

must_haves:
  truths:
    - "A missing cascade Redis Function makes the FCALL error propagate (no recovery) — pre-#284 behavior."
    - "NOSCRIPT/EVALSHA self-heal (handle_noscript_error) remains fully intact."
    - "extract_annotation and arun_fcall stay deleted; the 3 integration helpers keep calling client.fcall directly."
    - "No orphaned functions or unused imports remain in rapyer/ after removals."
    - "Full fakeredis unit suite and cascade integration tests pass on :6370."
  artifacts:
    - path: rapyer/scripts/registry.py
      provides: "Stateless script registry without any cascade self-heal helpers"
      contains: "run_fcall"
    - path: rapyer/context.py
      provides: "Bare pipe.execute() at both execute sites, no lazy registry import"
    - path: rapyer/errors/cascade.py
      provides: "Cascade errors minus PersistentCascadeFunctionError"
  key_links:
    - from: rapyer/base.py
      to: rapyer/scripts/registry.py
      via: "run_fcall enqueue only (no self-heal at execute)"
      pattern: "scripts_registry\\.run_fcall"
---

<objective>
Revert the issue-#284 cascade-function self-heal wired by quick task 260720-luc, deferring #284 to its own future ticket. Keep the KEPT part of 260720-luc (dead-code removal of `extract_annotation` and `arun_fcall`). Production behavior returns to pre-#284: a missing cascade Redis Function lets the FCALL error propagate with no recovery. The unrelated NOSCRIPT/EVALSHA self-heal stays intact.

Purpose: #284 self-heal is being deferred; the interim wiring is dead weight and must not linger.
Output: Four execute sites restored to bare `pipe.execute()`, six self-heal helpers + one error class removed, one test deleted, stale comments fixed, zero orphaned symbols.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md

<notes>
- Worktree: run `uv sync --extra test --group dev` once before pytest.
- Real Redis 7+ with RedisJSON is redis-stack on localhost:6370 (integration conftest targets it); :6379 has no JSON.
- ruff --fix save hook strips unused imports — remove each dying import together with its last use in the same edit.
- This is a targeted reversal, NOT a git revert (self-heal commits interleave with the KEPT arun_fcall-removal commit; a mechanical revert would conflict).
</notes>

<interfaces>
KEEP in rapyer/scripts/registry.py (all still used): run_fcall, register_cascade_function,
handle_noscript_error, arun_sha, run_sha, get_scripts, get_scripts_fakeredis, register_scripts,
_REGISTERED_SCRIPT_SHAS, get_script, build_script_texts, _build_scripts, _inject_sf_dispatch.

Pre-#284 _apipeline (rapyer/base.py) shape to restore — NOSCRIPT-only, plus exact ignore_redis_error swallow:
  yield pipe
  commands_backup = list(pipe.command_stack)
  noscript_on_first_attempt = False
  noscript_on_retry = False
  try:
      await pipe.execute()
  except NoScriptError:
      noscript_on_first_attempt = True
  except ResponseError as exc:
      if ignore_redis_error:
          logger.warning("Swallowed ResponseError ... %s", exc)   # swallow, do NOT raise
      else:
          raise
  if noscript_on_first_attempt: <existing EVALSHA reload-and-replay block — unchanged>
  if noscript_on_retry: raise PersistentNoScriptError(...)
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Restore the four bare-execute sites and strip self-heal helpers from registry.py</name>
  <files>rapyer/context.py, rapyer/base.py, rapyer/scripts/registry.py</files>
  <action>
Restore the four #284 execute sites to their pre-self-heal bare form and delete the now-unused registry helpers.

context.py:
- `ensure_pipeline`: replace the `if should_execute:` body's `await scripts_registry.aexecute_pipeline_with_cascade_self_heal(pipe, meta)` with plain `await pipe.execute()`. Remove the lazy `from rapyer.scripts import registry as scripts_registry` import that was added inside this function.
- `pipeline_with_execution`: replace `await scripts_registry.aexecute_pipeline_with_cascade_self_heal(pipe, meta)` with plain `await pipe.execute()`. Remove its lazy `from rapyer.scripts import registry as scripts_registry` import.

base.py:
- `aset_ttl` (~630): replace `results = await scripts_registry.aexecute_pipeline_with_cascade_self_heal(pipe, self.Meta)` with `results = await pipe.execute()`.
- `_apipeline` (~1391-1444): remove the `missing_function_on_first_attempt` flag declaration, the FCALL-missing detection in the `except ResponseError` branch (the `elif (not _meta.is_fake_redis and any(... FCALL ...) and await scripts_registry.acascade_function_missing(_meta))` clause), and the entire `if missing_function_on_first_attempt:` reload-and-replay block. Restore the plain form shown in <interfaces>: NoScriptError sets the noscript flag; the `except ResponseError as exc` branch logs+swallows when `ignore_redis_error` else re-raises; keep the existing NOSCRIPT EVALSHA reload-and-replay block and the `PersistentNoScriptError` raise untouched. Do NOT change base.py imports — `ResponseError`, `NoScriptError`, `PersistentNoScriptError`, and `scripts_registry` (still used by run_fcall) all remain in use.

registry.py — delete these six now-unused functions entirely: `aexecute_pipeline_with_cascade_self_heal`, `aretry_fcall_after_missing_function`, `acascade_function_missing`, `_pipeline_has_fcall`, `_name_in_function_list`, `handle_missing_function`. Then remove imports that become unused as a side effect (verified only these functions used them): drop `PersistentCascadeFunctionError` from the `rapyer.errors` import; change `from redis.exceptions import NoScriptError, ResponseError` to `from redis.exceptions import NoScriptError` (ResponseError only lived in the deleted helpers); remove `from rapyer.cascade.planner import build_cascade_plan, cascade_plan_json` entirely (only `handle_missing_function` used it — `register_cascade_function` uses `build_cascade_library` from loader, which stays).
  </action>
  <verify>
    <automated>! grep -rn "aexecute_pipeline_with_cascade_self_heal\|aretry_fcall_after_missing_function\|acascade_function_missing\|_pipeline_has_fcall\|_name_in_function_list\|handle_missing_function" rapyer/ && python -c "import rapyer" && echo OK</automated>
  </verify>
  <done>All four execute sites call bare `pipe.execute()`; six helpers deleted; registry.py imports NoScriptError only, no PersistentCascadeFunctionError, no cascade.planner import; `import rapyer` succeeds.</done>
</task>

<task type="auto">
  <name>Task 2: Remove PersistentCascadeFunctionError, delete self-heal test, fix stale comments</name>
  <files>rapyer/errors/cascade.py, rapyer/errors/__init__.py, tests/integration/foreign_keys/test_cascade_self_heal.py, rapyer/config.py, rapyer/scripts/registry.py</files>
  <action>
errors/cascade.py: delete ONLY the `PersistentCascadeFunctionError` class (lines ~24-25). Keep InvalidCascadeDepthError, CascadeTargetTtlMissingError, MetaFrozenError, CascadeLuaLiteralError.

errors/__init__.py: remove `PersistentCascadeFunctionError` from the `from rapyer.errors.cascade import (...)` block and remove its `"PersistentCascadeFunctionError",` entry from `__all__`.

Delete the file tests/integration/foreign_keys/test_cascade_self_heal.py (use `git rm` or Bash rm). Leave test_cascade_ttl_apply.py, test_cascade_depth_and_gate.py, test_cascade_graph_shapes.py as-is (they already call client.fcall directly).

config.py (`__setattr__` comment ~83-85): the exemption for `cascade_function_name` STAYS (init.py:100 still assigns it post-freeze). Only fix the comment: replace the wording that says the value is one "the cascade self-heal path (handle_missing_function) rewrites at runtime" with wording that it is a DERIVED hash value assigned post-freeze by `init_rapyer()` — no reference to any self-heal path (which no longer exists).

registry.py `run_fcall` comment (~159): currently "Enqueue only; self-heal happens at execute time (aexecute_pipeline_with_cascade_self_heal)." Replace with a neutral note that does not reference the removed helper, e.g. that it enqueues only and that self-heal for a missing cascade function is a future follow-up (issue #284).
  </action>
  <verify>
    <automated>! grep -rn "PersistentCascadeFunctionError\|test_cascade_self_heal" rapyer/ tests/ && ! grep -rn "handle_missing_function\|aexecute_pipeline_with_cascade_self_heal" rapyer/ && python -c "import rapyer.errors; assert not hasattr(rapyer.errors, 'PersistentCascadeFunctionError')" && echo OK</automated>
  </verify>
  <done>PersistentCascadeFunctionError gone from cascade.py + __init__.py + __all__; self-heal test deleted; config.py and run_fcall comments reference no deleted symbols; freeze-exemption for cascade_function_name preserved.</done>
</task>

<task type="auto">
  <name>Task 3: Orphan sweep and full test verification</name>
  <files>rapyer/, tests/</files>
  <action>
Run `uv sync --extra test --group dev` once (worktree). Confirm zero references remain in rapyer/ and tests/ to every removed symbol: `handle_missing_function`, `aexecute_pipeline_with_cascade_self_heal`, `aretry_fcall_after_missing_function`, `acascade_function_missing`, `_pipeline_has_fcall`, `_name_in_function_list`, `PersistentCascadeFunctionError`, `arun_fcall`, `extract_annotation`. Also confirm no OTHER function/import became unused as a side effect (ruff F401 catches unused imports; also eyeball registry.py imports). Then run the full fakeredis unit suite and the cascade integration tests on :6370, plus ruff/black/mypy.
  </action>
  <verify>
    <automated>! grep -rn "handle_missing_function\|aexecute_pipeline_with_cascade_self_heal\|aretry_fcall_after_missing_function\|acascade_function_missing\|_pipeline_has_fcall\|_name_in_function_list\|PersistentCascadeFunctionError\|arun_fcall\|extract_annotation" rapyer/ tests/; uv run ruff check . && uv run black --check . && uv run pytest tests/unit -q && REDIS_DB=0 uv run pytest tests/integration/foreign_keys -q</automated>
  </verify>
  <done>Grep returns no matches for any removed symbol; ruff + black clean; fakeredis unit suite green; cascade integration tests green on :6370.</done>
</task>

</tasks>

<verification>
- `import rapyer` succeeds and `rapyer.errors` no longer exposes PersistentCascadeFunctionError.
- Four execute sites (context.py x2, base.py aset_ttl, base.py _apipeline) use bare `pipe.execute()`.
- NOSCRIPT/EVALSHA self-heal path (handle_noscript_error + the noscript reload-and-replay block) unchanged and still tested by test_pipeline_noscript_recovery.py.
- No orphaned symbols or unused imports remain (ruff F401 + explicit grep sweep).
</verification>

<success_criteria>
- Missing cascade Redis Function propagates the FCALL error (no recovery) — pre-#284 state.
- 260720-luc dead-code removal (extract_annotation, arun_fcall) untouched and stays removed.
- config.py freeze-exemption for cascade_function_name preserved; only its comment corrected.
- Full fakeredis unit suite + cascade integration tests pass on :6370; ruff/black/mypy clean.
</success_criteria>

<output>
Write `.planning/quick/260720-odi-revert-284-cascade-self-heal-defer-to-fu/260720-odi-SUMMARY.md` when done.
</output>
