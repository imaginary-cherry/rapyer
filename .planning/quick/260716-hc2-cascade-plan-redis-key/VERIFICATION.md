---
phase: quick/260716-hc2-cascade-plan-redis-key
verified: 2026-07-16T00:00:00Z
status: passed
score: 8/8 must-haves verified
commit: 237ce7e
branch: cascade-ttl-full-review
---

# QUICK Verification: Store cascade plan in one Redis key read server-side

**Goal:** Move the cascade plan from per-call ARGV delivery (`_cascade_plan_arg` /
`reachable_plan_subset`) to a single Redis key (`CASCADE_PLAN_KEY =
"__rapyer_cascade_plan__"`) written once at `init_rapyer`; the Lua `GET`s + decodes it
server-side each call, with only the key NAME sent as ARGV[5]. Must preserve TTL
propagation, atomicity, dangling counts, and `CascadeResult`.

**Status:** PASS — goal achieved, no cascade regression.

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `CASCADE_PLAN_KEY` constant defined | ✓ VERIFIED | `rapyer/types/special.py:8` — `CASCADE_PLAN_KEY = "__rapyer_cascade_plan__"` next to `SPECIAL_FIELD_KEY_PREFIX` |
| 2 | `reachable_plan_subset` removed; `cascade_plan_json` serializes full plan | ✓ VERIFIED | `planner.py` — no `reachable_plan_subset`; `cascade_plan_json` (`:293`) uses `dataclasses.asdict` + `_drop_none_values` (`:280`) + `json.dumps` over the full plan dict; comment updated to "written once to a Redis key" |
| 3 | Lua reads plan from ARGV[5] key, degrades on miss | ✓ VERIFIED | `apply.lua:8-10` — `local plan_raw = redis.call('GET', ARGV[5])` / `local CASCADE_PLAN = plan_raw and cjson.decode(plan_raw) or {}` / `local classes = CASCADE_PLAN`. Read/write phases unchanged: `queue_special_refresh` (`:61`), `fk_edges` (`:71`), `next_hop` (`:145`), write-phase `classes[item.class].ttl` (`:311`), dangling counters (`:308-319`), root main key queued unconditionally (`:264`) |
| 4 | init writes plan key before `register_scripts` | ✓ VERIFIED | `init.py:84-85` builds+validates plan in try; `:92-97` `if redis is not None:` → `await redis.set(CASCADE_PLAN_KEY, cascade_plan_json(plan))` BEFORE `register_scripts`. Imports: `cascade_plan_json` (`:11`), `CASCADE_PLAN_KEY` (`:17`); no `reachable_plan_subset` |
| 5 | `_cascade_plan_arg` ClassVar removed; both call sites pass `CASCADE_PLAN_KEY`; script always runs | ✓ VERIFIED | `base.py` import (`:87-89`); `refresh_ttl` final arg `CASCADE_PLAN_KEY` (`:269`); `aset_ttl` final arg `CASCADE_PLAN_KEY` (`:621`); no `_cascade_plan_arg`, no `_has_cascade` branch (the one `_has_cascade` grep hit is an unrelated test function name) |
| 6 | Three init-emulating fixtures write full plan key after `register_scripts`, correct MODELS scope | ✓ VERIFIED | `tests/integration/conftest.py:55,60` (REDIS_MODELS); `tests/integration/foreign_keys/conftest.py:58,61` (CASCADE_INTEGRATION_MODELS); `tests/unit/cascade/conftest.py:123,126` (CASCADE_PLANNER_MODELS) — each `.set(...)` follows `register_scripts` |
| 7 | Zero `_cascade_plan_arg` / `reachable_plan_subset` repo-wide | ✓ VERIFIED | `grep -rn` in `rapyer/ tests/` → 0 for both |
| 8 | Mock `.set` stubs present; init test asserts plan set; no-edge test deleted | ✓ VERIFIED | `.set = AsyncMock()` at `test_init_rapyer.py:37,125`, `test_meta_ttl_freeze.py:18`, `test_init_rapyer_cascade_ttl.py:17`. Rewritten `test_init_rapyer_writes_full_cascade_plan_key_sanity` (`test_init_rapyer.py:256`) scans `set.await_args_list`/`call_args_list`, finds `CASCADE_PLAN_KEY` call, `json.loads(args[1])`, asserts every registered class present. `test_init_rapyer_no_edge_model_ships_only_its_own_class_sanity` deleted (grep count 0) |

**Score:** 8/8 truths verified.

## Behavior-Preservation Checks

- Write phase splits root TTL (`root_ttl`) vs child owning-class TTL (`classes[item.class].ttl`) — unchanged (`apply.lua:311`).
- Dangling counters (`dangling_children_count`, `dangling_special_count`) and return tuple unchanged (`apply.lua:308-322`).
- Root main + special keys queued unconditionally; `do_cascade` gate only controls edge walk (`apply.lua:264-275`) — unchanged.
- Script ALWAYS runs; no `_has_cascade` short-circuit. EVALSHA/atomicity/`CascadeResult` untouched.
- Degrade path: missing/deleted key → `GET` returns false → `or {}` → root-own-keys-only refresh, no raise. Covered by `test_cascade_apply_with_deleted_plan_key_degrades_to_root_only` (PASS).

## Gate Results

| Gate | Result |
|------|--------|
| `black --check rapyer tests` | PASS — 306 files unchanged |
| `ruff check rapyer tests` | PASS — All checks passed |
| `tests/unit/cascade` (real Redis :6370, isolated) | 93 passed |
| `tests/integration/foreign_keys` (real Redis :6370, isolated) | 29 passed |
| Degrade-path test | PASS (1) |
| Full-plan integration test `test_cascade_plan_key_written_at_init_and_drives_subtree_refresh` | PASS (1) |
| noscript-recovery: `test_pipeline_noscript_recovery.py` + `test_scripts.py` | 8 passed |

**Note on cascade NOSCRIPT:** Cascade paths deliberately do NOT self-heal NOSCRIPT
(scoped out; tracked follow-up issue #284, `base.py:626`). No cascade-specific
noscript-recovery test exists to run; the shared registry recovery machinery this
change touches indirectly is covered by the 8 passing tests above.

## Pre-existing Errors (NOT regressions)

Running the combined slice `tests/unit/cascade tests/integration/foreign_keys` together
yields 29 ERRORs, all identical:

```
TypeError: object MagicMock can't be used in 'await' expression
tests/integration/conftest.py:40: await redis.flushdb()
```

Root cause: the mock-based unit tests leave `AtomicRedisModel.Meta.redis` as a
`MagicMock`, which the autouse integration `real_redis_client` fixture then tries to
`await`. This is cross-module fixture isolation, unrelated to this change.

**Confirmed pre-existing on HEAD~1 (7d1e01e):** the exact same combo produces 28 ERRORs
with the identical `MagicMock can't be used in 'await'` signature at
`tests/integration/conftest.py:40`. The 28→29 delta is explained by this change's test
count differences (deleted no-edge test, reworked injection/init tests), not a new
failure. Both suites pass cleanly in isolation (93 + 29).

## Conclusion

PASS. All 8 must-haves verified against actual code at commit 237ce7e. The cascade plan
now lives in one Redis key written once before `register_scripts`; the Lua reads and
decodes it server-side per call; only the key name is shipped as ARGV[5]. Per-call ARGV
subset delivery is fully removed repo-wide. TTL propagation, atomicity, dangling counts,
and `CascadeResult` are behavior-preserved, including the accepted O(all registered)
decode tradeoff. Lint clean; all cascade/FK tests green in isolation; the only combined-run
errors are a confirmed pre-existing fixture-isolation issue.

---
_Verified: 2026-07-16_
_Verifier: Claude (gsd-verifier)_
