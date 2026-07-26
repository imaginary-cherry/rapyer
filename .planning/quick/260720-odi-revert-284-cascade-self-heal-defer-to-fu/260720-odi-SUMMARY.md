---
phase: quick-260720-odi
plan: 01
subsystem: cascade / scripts registry
tags: [revert, cascade, ttl, redis-functions, cleanup]
requires: []
provides: [pre-284-fcall-error-propagation, stateless-registry-no-cascade-self-heal]
affects: [rapyer/context.py, rapyer/base.py, rapyer/scripts/registry.py, rapyer/errors/cascade.py, rapyer/errors/__init__.py, rapyer/config.py]
tech-stack:
  added: []
  patterns: [bare-pipe-execute, noscript-only-self-heal]
key-files:
  created: []
  modified:
    - rapyer/context.py
    - rapyer/base.py
    - rapyer/scripts/registry.py
    - rapyer/errors/cascade.py
    - rapyer/errors/__init__.py
    - rapyer/config.py
  deleted:
    - tests/integration/foreign_keys/test_cascade_self_heal.py
decisions:
  - "Targeted reversal (not git revert) of #284 self-heal; kept 260720-luc dead-code removal (extract_annotation, arun_fcall stay deleted)."
  - "Missing cascade Redis Function now propagates the FCALL ResponseError with no recovery - the correct deferred (#284) state."
  - "NOSCRIPT/EVALSHA self-heal (handle_noscript_error + reload-replay) left fully intact and still tested."
metrics:
  duration: ~12m
  completed: 2026-07-20
  tasks: 3
  files_changed: 6
  files_deleted: 1
---

# Phase quick-260720-odi Plan 01: Revert #284 Cascade Self-Heal (Defer to Future) Summary

Reverted the issue-#284 cascade-function self-heal wiring introduced by quick task 260720-luc, restoring pre-#284 behavior where a missing cascade Redis Function lets the FCALL error propagate with no recovery - while keeping 260720-luc's dead-code removal and the unrelated NOSCRIPT/EVALSHA self-heal intact.

## What Was Done

### Task 1 - Restore bare-execute sites, strip self-heal helpers (commit 81d0361)
- context.py: ensure_pipeline and pipeline_with_execution now call bare await pipe.execute(); removed both lazy registry imports.
- base.py: aset_ttl uses results = await pipe.execute(); _apipeline reverted to the NOSCRIPT-only shape - removed the missing_function_on_first_attempt flag, the FCALL-missing detection in the except ResponseError branch, and the reload-and-replay block. The ignore_redis_error swallow and the NOSCRIPT EVALSHA reload-replay + PersistentNoScriptError raise are untouched. base.py imports unchanged (ResponseError, NoScriptError, PersistentNoScriptError, scripts_registry all still used).
- registry.py: deleted six helpers (aexecute_pipeline_with_cascade_self_heal, aretry_fcall_after_missing_function, acascade_function_missing, _pipeline_has_fcall, _name_in_function_list, handle_missing_function). Import cleanup: NoScriptError only (dropped ResponseError), dropped PersistentCascadeFunctionError, removed the rapyer.cascade.planner import. run_fcall comment now references issue #284 as future follow-up.

### Task 2 - Remove error class, delete test, fix stale comments (commit 563e502)
- errors/cascade.py: deleted PersistentCascadeFunctionError (kept the other four cascade errors).
- errors/__init__.py: removed the import and the __all__ entry.
- Deleted tests/integration/foreign_keys/test_cascade_self_heal.py (76 lines).
- config.py: cascade_function_name freeze-exemption preserved; comment reworded to say it is a DERIVED hash assigned post-freeze by init_rapyer(), no reference to any (now-removed) self-heal path.

### Task 3 - Orphan sweep and full verification
- Grep sweep across rapyer/ and tests/: zero references to all nine removed symbols (six helpers + PersistentCascadeFunctionError + arun_fcall + extract_annotation).

## Deviations from Plan

None functionally. One process note: the Task 2 git add included the already-git-rm'd test path, which aborted the add before staging the three modified files; the initial commit captured only the deletion. Corrected via git commit --amend to include config.py, errors/__init__.py, errors/cascade.py (final Task 2 commit 563e502). No behavior impact.

Pre-existing multi-line comments in registry.py/base.py/config.py triggered the comment-style hook nudge; left as-is since they predate this task and are out of the revert's scope (only the config.py exemption comment I touched was reworded, keeping its existing multi-line form for file consistency).

## Verification Results (actual counts)

- uv run pytest tests/unit -q -> 800 passed, 6 warnings
- uv run pytest tests/integration/foreign_keys -q (:6370) -> 40 passed
- uv run ruff check . -> All checks passed!
- uv run black --check . -> 323 files unchanged (clean)
- uv run mypy ... tests/models -> exit 0 (clean)
- NOSCRIPT recovery tests (-k noscript) -> 8 passed (self-heal path confirmed intact)
- import rapyer succeeds; rapyer.errors no longer exposes PersistentCascadeFunctionError.

## Self-Check: PASSED

- context.py, base.py, registry.py, errors/cascade.py, errors/__init__.py, config.py all modified and present.
- test_cascade_self_heal.py deleted.
- Commits 81d0361 and 563e502 present on worktree branch.
