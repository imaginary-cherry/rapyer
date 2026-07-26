---
phase: quick-260720-luc
plan: 01
subsystem: cascade-ttl / scripts
tags: [cascade, self-heal, redis-functions, dead-code, tdd]
requires:
  - Redis Functions cascade library (register_cascade_function / handle_missing_function)
  - RedisConfig.cascade_function_name (freeze-exempt)
provides:
  - Shared cascade self-heal on all four production FCALL execute sites
  - acascade_function_missing registry-based missing-function detection
affects:
  - rapyer/scripts/registry.py
  - rapyer/context.py
  - rapyer/base.py
  - rapyer/config.py
tech-stack:
  added: []
  patterns:
    - "Registry-based (FUNCTION LIST) missing-function detection — async pipeline masks the error text"
    - "Single retry then PersistentCascadeFunctionError (bounded self-heal)"
key-files:
  created:
    - tests/integration/foreign_keys/test_cascade_self_heal.py
  modified:
    - rapyer/utils/annotation.py
    - rapyer/scripts/registry.py
    - rapyer/scripts/__init__.py
    - rapyer/context.py
    - rapyer/base.py
    - rapyer/config.py
    - tests/integration/foreign_keys/test_cascade_ttl_apply.py
    - tests/integration/foreign_keys/test_cascade_depth_and_gate.py
    - tests/integration/foreign_keys/test_cascade_graph_shapes.py
  deleted:
    - tests/unit/cascade/test_extract_annotation.py
decisions:
  - "Detect a missing cascade function via FUNCTION LIST (acascade_function_missing), not error-string matching — redis-py's async pipeline annotate_exception (client.py:1585) overwrites exception.args with a non-f-string literal, destroying the 'Function not found' text on every pipelined FCALL"
metrics:
  duration: ~14min
  tasks: 4
  files: 10
  completed: 2026-07-20
---

# Phase quick-260720-luc Plan 01: Remove Dead Cascade Helpers and Wire #284 Summary

Promoted the issue-#284 cascade-function self-heal from the test-only direct-client wrapper into every production TTL-cascade FCALL execute path, removed dead code (`extract_annotation`, `arun_fcall`), and added a real-Redis regression test — discovering and fixing a redis-py async-pipeline bug that made naive message-based detection impossible.

## What Was Built

- **Task 1** — Deleted unused `extract_annotation` from `rapyer/utils/annotation.py` and its sole test file. `has_annotation` / `field_with_flag` untouched.
- **Task 2** — Added two shared helpers to `rapyer/scripts/registry.py` (`aexecute_pipeline_with_cascade_self_heal`, `aretry_fcall_after_missing_function`) and wired all four bare-execute sites: `context.ensure_pipeline`, `context.pipeline_with_execution` (lazy import per the documented cycle), `base.aset_ttl`, and `base._apipeline`. Removed resolved #284 comments; updated the `config.py` freeze-exempt comment.
- **Task 3** — Removed the now-redundant `arun_fcall` (registry import + `__all__`) and rewrote the 3 integration `_apply_cascade` helpers to call `real_redis_client.fcall` directly. `handle_missing_function` and `PersistentCascadeFunctionError` retained (used by the new self-heal path).
- **Task 4 (TDD)** — Added `test_cascade_self_heal.py`: after `FUNCTION FLUSH`, `aset_ttl(cascade=True)` and `refresh_ttl()` transparently reload the function and refresh the whole reachable subtree without raising; `cascade_function_name` is repopulated.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Message-based missing-function detection never fires inside a pipeline**
- **Found during:** Task 4 (the RED test failed at GREEN-expected time)
- **Issue:** The plan specified detecting the missing function via `"function not found" in str(e).lower()` (mirroring the deleted `arun_fcall`). That worked for `arun_fcall` only because it called `client.fcall` **directly**. Every production FCALL runs **inside a pipeline**, and redis-py's async `Pipeline.annotate_exception` (`.venv/.../redis/asyncio/client.py:1585-1589`) rebuilds `exception.args` with a **non-f-string literal** (`"of pipeline caused error: {exception.args}"`), destroying the original "Function not found" text. So the string match could never match on any real production path.
- **Fix:** Added `acascade_function_missing(redis_config)` — an `a`-prefixed helper that scans `FUNCTION LIST` (RESP2/RESP3-shape agnostic via `_name_in_function_list`) to determine whether the current cascade function is loaded. The shared wrapper and `_apipeline` now self-heal only when: real Redis (not fakeredis) AND the pipeline enqueued an `FCALL` AND the function is genuinely absent. Any other `ResponseError` re-raises unchanged (preserves threat-register T-luc-03).
- **Files modified:** `rapyer/scripts/registry.py`, `rapyer/base.py`
- **Commit:** e577d3e

## TDD Gate Compliance

- RED: `097402f` — `test(...)` commit; the self-heal test failed because the helper string-matched a masked error message.
- GREEN: `e577d3e` — `fix(...)` commit; registry-based detection makes both self-heal tests pass.
- REFACTOR: none needed.

## Verification Results

- `uv run pytest tests/unit -q` → **800 passed**, 6 warnings (pre-existing pydantic RedisDatetimeTimestamp serializer warnings, unrelated).
- `uv run pytest tests/integration/foreign_keys -q` (real Redis :6370) → **42 passed** (includes the 2 new self-heal tests).
- `uv run ruff check .` → All checks passed.
- `uv run black --check .` → 324 files unchanged, clean.

## Notes

- fakeredis EXPIRE branch, existing `Meta.ttl`/`refresh_ttl` behavior, and single-FCALL atomicity all preserved.
- The retry rewrites only the function-name slot (`args[1]`) of each backed-up FCALL, keeping numkeys/keys/args verbatim (threat T-luc-01); a single retry then raises `PersistentCascadeFunctionError` (threat T-luc-02).
- `context.py` uses lazy in-function imports of `rapyer.scripts.registry` inside `ensure_pipeline` and `pipeline_with_execution` — the sanctioned documented-cycle exception per the plan's `<cycle_note>`.

## Commits

- bbb7393 — refactor: remove dead extract_annotation and its test
- dc2dca2 — feat: wire cascade self-heal into all four FCALL execute sites
- 70e52b4 — refactor: remove redundant arun_fcall, use client.fcall in test helpers
- 097402f — test: add cascade self-heal regression test (RED)
- e577d3e — fix: detect missing cascade function via registry, not error text (GREEN)

## Self-Check: PASSED
- `tests/integration/foreign_keys/test_cascade_self_heal.py` — FOUND
- `extract_annotation` / `arun_fcall` / `issue #284` references in rapyer/ and tests/ — NONE (removed)
- `handle_missing_function` / `PersistentCascadeFunctionError` — retained in registry.py
- All 5 commits present in git log; working tree clean.
