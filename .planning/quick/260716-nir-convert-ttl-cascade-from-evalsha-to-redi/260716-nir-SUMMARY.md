---
phase: quick-260716-nir
plan: 01
subsystem: cascade
tags: [cascade, ttl, redis-functions, fcall, lua, fakeredis]
requires: [CASCADE-FN-01]
provides:
  - "TTL cascade via Redis Functions (FUNCTION LOAD + FCALL)"
  - "Plan-hashed library/function names for server-global isolation"
  - "Root-own-keys EXPIRE fallback on fakeredis"
affects:
  - rapyer/scripts/lua/cascade/library.lua
  - rapyer/scripts/registry.py
  - rapyer/scripts/loader.py
  - rapyer/cascade/planner.py
  - rapyer/base.py
  - rapyer/init.py
tech-stack:
  added: []
  patterns: ["Redis Functions library (FCALL) replacing EVALSHA for cascade only"]
key-files:
  created:
    - tests/integration/foreign_keys/test_cascade_depth_and_gate.py
  modified:
    - rapyer/scripts/lua/cascade/library.lua
    - rapyer/scripts/loader.py
    - rapyer/scripts/registry.py
    - rapyer/scripts/__init__.py
    - rapyer/scripts/constants.py
    - rapyer/cascade/planner.py
    - rapyer/errors/cascade.py
    - rapyer/errors/__init__.py
    - rapyer/init.py
    - rapyer/base.py
    - rapyer/types/special.py
    - docs/documentation/special-fields/ttl-cascade.md
  deleted:
    - rapyer/scripts/lua/cascade/apply.lua
    - tests/unit/cascade/test_cascade_apply_lua.py
decisions:
  - "Bake the plan as a JSON string upvalue and cjson.decode lazily inside the FCALL callback (memoized) because cjson is unavailable at Redis Functions library-load scope"
  - "Hash the plan into BOTH library and function names so concurrent processes with different model sets do not clobber each other (server-global function namespace)"
  - "Detect fakeredis via Meta.is_fake_redis; on fakeredis skip loading the function and refresh only the root's own keys via EXPIRE"
metrics:
  duration: ~2h
  completed: 2026-07-16
---

# Phase quick-260716-nir Plan 01: Convert TTL Cascade from EVALSHA to Redis Functions Summary

Converted TTL cascade from an EVALSHA Lua script (with a per-call plan GET) to a Redis Functions library whose plan is baked into the source and decoded once, and made cascade traversal real-Redis-7+-only while keeping the root's own TTL refresh working on fakeredis.

## What Changed

- **Redis Functions library** (`rapyer/scripts/lua/cascade/library.lua`): converted `apply.lua` to a `#!lua name=...` library with a `cascade_apply` callback. All per-call mutable state (visited/pending_refresh/refresh_order/stack and closures touching them) lives inside the callback; pure helpers (fk_edges/read_reference_paths/next_hop/budget_is_larger) live at library scope. The plan is baked as a Lua long-bracket string upvalue and `cjson.decode`d lazily on first call (memoized) — `cjson` is not available at library-load scope.
- **Planner** (`rapyer/cascade/planner.py`): added `cascade_plan_hash`, `cascade_names` (hashes BOTH library and function names for server-global isolation), and `cascade_plan_lua_literal` (long-bracket wrap with a `]==]` guard raising `CascadeLuaLiteralError`).
- **Scripts layer**: `loader.build_cascade_library` substitutes the lib/fn/plan-literal tokens; `registry` adds `register_cascade_function`/`get_cascade_function_name`/`run_fcall`/`arun_fcall` (with missing-function self-heal → `PersistentCascadeFunctionError`); cascade dropped from the EVALSHA `SCRIPT_REGISTRY`.
- **init/base wiring**: `init_rapyer` loads the function on real Redis, skips it on fakeredis; `refresh_ttl`/`aset_ttl` branch on `Meta.is_fake_redis` — FCALL on real Redis, `all_keys` EXPIRE fallback on fakeredis. Stopped writing/passing `CASCADE_PLAN_KEY`.
- **Tests**: added a Redis-7+ gate fixture (`requires_redis_functions`); cascade fixtures now `register_cascade_function` instead of writing `CASCADE_PLAN_KEY`; ported fakeredis cascade-traversal tests to real Redis via `arun_fcall` (new `test_cascade_depth_and_gate.py`); non-cascade TTL tests stay dual-backend via the EXPIRE fallback.
- **Dead plumbing removed**: `apply.lua`, `CASCADE_TTL_APPLY_SCRIPT_NAME`, `CASCADE_PLAN_KEY` — zero remaining references in `rapyer/` and `tests/`.
- **Docs/CONCERNS**: documented the Redis-7+/Functions requirement and the exact fakeredis fallback; recorded the fakeredis divergence and the server-global plan-hashed-name mitigation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] cjson unavailable at Redis Functions library-load scope**
- **Found during:** Task 4 (first real-Redis FUNCTION LOAD)
- **Issue:** The plan specified decoding the baked plan at library scope (`local CASCADE_PLAN = cjson.decode(...)`). Real Redis raised `Error registering functions: ... nonexistent global variable 'cjson'` — the load phase only registers functions and does not expose `cjson`.
- **Fix:** Bake the plan as a raw JSON string upvalue and `cjson.decode` lazily inside the callback on first call, memoized into the `CASCADE_PLAN` upvalue (still decoded once, read-only, safe to share across calls).
- **Files:** rapyer/scripts/lua/cascade/library.lua
- **Commit:** cdfc3ef

**2. [Rule 3 - Blocking] Test files beyond the plan's file list referenced dead plumbing**
- **Found during:** Task 4
- **Issue:** `tests/unit/test_init_rapyer.py`, `tests/unit/test_refresh_ttl_if_needed.py`, `tests/unit/cascade/test_cascade_action_boundary.py`, `tests/integration/pipeline/test_pipeline_noscript_recovery.py`, and several mock-client fixtures referenced `CASCADE_PLAN_KEY`/`CASCADE_TTL_APPLY_SCRIPT_NAME`/`run_sha` or lacked `function_load` on their mock Redis.
- **Fix:** Updated them to the FCALL machinery: patch `run_fcall`, add `function_load = AsyncMock()` to mock clients, assert `function_load` source, and change the NOSCRIPT-recovery helper to rely on functions surviving `SCRIPT FLUSH`.
- **Commit:** cdfc3ef

**3. [Rule 3 - Blocking] fakeredis fixtures did not set `Meta.is_fake_redis`**
- **Found during:** Task 4
- **Issue:** `refresh_ttl`/`aset_ttl` branch on `Meta.is_fake_redis`, but the shared `fake_redis_client` fixture and several `setup_fake_redis` fixtures wired `Meta.redis` to fakeredis without setting the flag, so refresh took the real-Redis FCALL branch and failed (`ScriptsNotInitializedError`).
- **Fix:** The shared `fake_redis_client` fixture now sets `Meta.is_fake_redis = True` on all `REDIS_MODELS` (with restore) so fakeredis unit tests use the EXPIRE fallback.
- **Files:** tests/unit/conftest.py
- **Commit:** cdfc3ef

## Test Results

- Lint: `ruff check .` and `black --check .` pass.
- Unit (fakeredis): 804 passed.
- Cascade integration (real Redis 7.4.7 @ localhost:6370, RedisJSON + RediSearch + Functions): 40 passed.
- Full suite (`REDIS_DB=0 uv run --extra test pytest -q`): **2416 passed, 205 skipped, 0 failed** — no non-cascade regressions.
- Grep confirms zero references to `CASCADE_PLAN_KEY`, `CASCADE_TTL_APPLY_SCRIPT_NAME`, or `apply.lua` in `rapyer/`/`tests/`.

## Notes

- The pipelined `refresh_ttl`/`aset_ttl` FCALL path intentionally does NOT self-heal a missing function (matches the prior EVALSHA-in-pipeline behavior; issue #284). Only the direct `arun_fcall` path self-heals.
- CONCERNS.md (under `.planning/`) was updated with the two new fakeredis/real-Redis divergence entries; not committed by the executor (docs commit handled by the orchestrator).

## Self-Check: PASSED
- All created/modified artifacts exist on disk.
- Commits present: 2099c9c, 729d76f, 64c525d, cdfc3ef (Task 4, amended), ed03eb0.
- apply.lua removed; grep clean.
