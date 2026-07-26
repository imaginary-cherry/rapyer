---
quick_id: 260714-l0p
status: complete
date: 2026-07-14
commit: e10ad4e
branch: cascade-ttl-full-review
---

# Quick Task 260714-l0p — Fix 9 failing tests on PR #283

## Outcome

Full suite green: **2424 passed, 205 skipped, 0 failures** (was 9 failed).
Test-only changes — no `rapyer/` production code touched. Commit `e10ad4e`.

## Root causes (both test-isolation, not product bugs)

**Cause B — 7 cascade unit failures** (`test_cascade_apply_lua.py`, `test_cascade_plan_table.py`)
`init_rapyer()` authoritatively sets `model.Meta.cascade_ttl = cascade_ttl` for every
registered model (default `None`) — a deliberate, tested contract
(`test_init_rapyer_cascade_ttl.py::test_init_rapyer_without_cascade_ttl_resets_prior_value_to_none_sanity`).
Any prior `init_rapyer()` in the suite permanently wipes each model's class-declared
`Meta.cascade_ttl` (e.g. `CascadeBlanketRoot` → `CascadeTTL(depth=2)`). The cascade
fixtures only snapshot/restore `redis`/`is_fake_redis`, so the blanket cascade config
was gone → planner produced 0 edges → traversal stopped early. Passed alone (no prior
`init_rapyer()`), failed in the full suite.

**Cause A — 2 integration failures**
`refresh_ttl` now ALWAYS runs the cascade Lua script, so `asave()` on a TTL model needs
scripts loaded. Two tests cleared/flushed scripts BEFORE `asave()`, so the expected error
fired during Arrange instead of inside `pytest.raises`.

## Fixes

- `tests/unit/cascade/conftest.py`: snapshot each `CASCADE_PLANNER_MODELS` class's
  declared `Meta.cascade_ttl` at conftest import (before any `init_rapyer()` runs); both
  cascade fixtures re-establish it on setup and restore the pre-fixture value on teardown.
- `tests/integration/lst/test_redis_list_remove_range.py`: the ScriptsNotInitialized test
  now saves the model first, then clears `_REGISTERED_SCRIPT_SHAS` inline (try/finally
  restore) so only the pipeline `remove_range` hits the missing script.
- `tests/integration/pipeline/test_pipeline_noscript_recovery.py`: the persistent-NOSCRIPT
  test drops the `flush_scripts` fixture, saves the model, then `SCRIPT FLUSH`es manually
  before the `pytest.raises` block.

## Design note (not acted on — flagged for the user)

The `init_rapyer()` contract wipes per-model `Meta.cascade_ttl` on any call without an
explicit `cascade_ttl=` argument. A real user setting `Meta = RedisConfig(cascade_ttl=...)`
per-model and then calling `init_rapyer(redis_url)` at startup would silently lose that
config. It is deliberate and tested, so out of scope here — but worth revisiting as a
possible footgun (a sentinel default would let "unset" differ from an explicit "None").
