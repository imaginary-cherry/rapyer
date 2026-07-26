---
phase: quick/260716-fft-cascade-plan-per-call-argv
verified: 2026-07-16T00:00:00Z
status: passed
score: 5/5 must-haves verified
commit: 7d1e01e24c97e9a660a52ad298c083ffeeeae1dd
branch: cascade-ttl-full-review
overrides_applied: 0
---

# Cascade Plan Per-Call ARGV[5] — Verification Report

**Goal:** Replace SCRIPT-LOAD-time baking of the full per-class CASCADE_PLAN Lua
table with a per-call JSON `ARGV[5]` carrying only the root's transitively-reachable
plan subset, precomputed + cached at `init_rapyer`. Performance fix; must be
behavior-preserving for cascade TTL propagation, atomicity, dangling counts, and
the CascadeResult API.

**Status:** PASSED — goal achieved, no regressions found.

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Lua script no longer bakes any per-class plan at SCRIPT LOAD | ✓ VERIFIED | `apply.lua:9` `local CASCADE_PLAN = cjson.decode(ARGV[5] or '{}')`; `--[[CASCADE_PLAN_TABLE]]` grep-absent from `rapyer/` and `tests/` |
| 2 | Each root ships only its reachable-plan subset as JSON in ARGV[5] | ✓ VERIFIED | `planner.py:280-307` reachable_plan_subset; wired via `init.py:88-91` → `base.py:269,619` |
| 3 | Per-call cost is O(reachable classes), not O(all registered) | ✓ VERIFIED | `test_init_rapyer.py:278-279` asserts no-edge model subset `<= {model.__name__}` |
| 4 | aset_ttl and refresh_ttl still ALWAYS run the cascade script (no branch flag) | ✓ VERIFIED | `base.py:250-271` refresh_ttl and `base.py:597-620` aset_ttl both unconditionally call run_sha; no `_has_cascade` reintroduced (grep clean) |
| 5 | Existing behavior (dangling counts, graph shapes, depth budgets, noscript, CascadeResult) unchanged | ✓ VERIFIED | apply.lua read/write phases byte-unchanged below the header; full suite 2434 passed incl. dangling/graph-shape/depth-budget tests |

**Score: 5/5**

## Artifact Verification

### 1. rapyer/scripts/lua/cascade/apply.lua
- Placeholder `--[[CASCADE_PLAN_TABLE]]` GONE; replaced by `cjson.decode(ARGV[5] or '{}')` at line 9, `local classes = CASCADE_PLAN` at line 10.
- Everything downstream unchanged and verified: `queue_special_refresh` (nil-entry guard `if not entry then return`, line 61-69), `fk_edges` (nil guard, line 71-77), `next_hop` budget logic (145-163), write-phase ttl lookup `item.is_root and root_ttl or classes[item.class].ttl` (line 311), dangling counters (308-320) unchanged. ARGV[1..4] semantics unchanged.

### 2. rapyer/cascade/planner.py
- `reachable_plan_subset` (280-307): DFS over `edge.target`; always includes root if in plan; `visited` set makes it cycle-safe; `plan.get(name)` skips absent targets without KeyError; depth ignored (follows every edge). Correct closure — no-edge → {itself}; diamond/cycle terminates and includes all reachable.
- `cascade_plan_json` (323-329): `dataclasses.asdict` per entry, `_drop_none_values` recursively drops None (depth/ttl vanish), `json.dumps(separators=(",", ":"))` compact. `import json` at module top (line 2).

### 3. rapyer/scripts/registry.py
- `_inject_cascade_plan`, `_lua_literal`, `CASCADE_PLAN_PLACEHOLDER`, `asdict` import, `build_cascade_plan` import all REMOVED (grep clean).
- `build_script_texts` (87-100) does SF-dispatch injection only. `register_scripts`/`run_sha`/`arun_sha`/`handle_noscript_error`/`SCRIPT_REGISTRY`/`SF_DISPATCH_PLACEHOLDER` intact.

### 4. rapyer/base.py
- `_cascade_plan_arg: ClassVar[str] = "{}"` at line 176 on AtomicRedisModel.
- refresh_ttl (258-270): `self._cascade_plan_arg` appended as FINAL run_sha arg after cascade flag `1` → ARGV[5], with WHY comment.
- aset_ttl (610-619): `self._cascade_plan_arg` appended as FINAL arg after `1 if cascade else 0` → ARGV[5].
- No `_has_cascade` branch; both methods always run the script.

### 5. rapyer/init.py
- Module-top import `from rapyer.cascade.planner import (build_cascade_plan, cascade_plan_json, reachable_plan_subset, validate_cascade_ttl_targets)` (9-15).
- `plan = build_cascade_plan(...)` + `validate_cascade_ttl_targets(plan)` once, then per-model `model._cascade_plan_arg = cascade_plan_json(reachable_plan_subset(plan, model.__name__))` (84-91) INSIDE the try, BEFORE the finally refreeze (92-96).

### 6. Tests
- Mock assertions read `type(model)._cascade_plan_arg` (NOT literal `"{}"`) in test_aset_ttl_cascade_flag.py, test_refresh_ttl_cascade_branch.py; test_cascade_apply_lua.py appends `type(root)._cascade_plan_arg` to arun_sha; test_cascade_action_boundary.py unchanged (args[1] check).
- Syntax test asserts placeholder ABSENT + `cjson.decode(ARGV[5]` present (test_cascade_apply_lua_syntax.py:12-13).
- test_cascade_plan_injection.py rewritten: tests reachable_plan_subset (cycle/diamond/unreachable/root-only/transitive/absent-target) + cascade_plan_json (None omission + json round-trip).
- test_init_rapyer.py: dead CASCADE_PLAN_PLACEHOLDER/_inject_cascade_plan imports dropped; asserts SF-only injection; verifies _cascade_plan_arg populated + no-edge O(reachable).
- All THREE emulated-init conftests cache `_cascade_plan_arg` with a REAL reachable subset (not empty): tests/unit/cascade/conftest.py:125-129, tests/integration/foreign_keys/conftest.py:60-63, tests/integration/conftest.py:57-60. Verified — without this the emulated-init tests would silently pass on an empty plan.

## Gates Run

| Gate | Command | Result |
|------|---------|--------|
| black | `black --check rapyer tests` | ✓ clean (306 files unchanged) |
| ruff | `ruff check rapyer tests` | ✓ All checks passed |
| unit cascade | `REDIS_DB=0 pytest tests/unit/cascade -q -p no:randomly` | ✓ 96 passed |
| integration FK | `REDIS_DB=0 pytest tests/integration/foreign_keys -q -p no:randomly` | ✓ 28 passed |
| full suite | `REDIS_DB=0 pytest tests -q -p no:randomly` | ✓ 2434 passed, 205 skipped, 0 failures/errors (101s) |

Real Redis Stack on localhost:6370 reachable (PONG).

## Note on the requested narrow slice

`REDIS_DB=0 pytest tests/unit/cascade tests/integration/foreign_keys` reports 96 passed
/ 28 errors. Investigated: the 28 errors are ALL setup errors in
`tests/integration/conftest.py:40` `redis_client` fixture, which reads global
`AtomicRedisModel.Meta.redis` — left as a `MagicMock` by a preceding unit test
(`await redis.flushdb()` → "object MagicMock can't be used in 'await' expression").

This is a PRE-EXISTING cross-module fixture-isolation issue, NOT a regression:
- The parent commit (7d1e01e~1) produces the identical failure with the same command
  (91 passed / 27 errors). Current commit differs only by +5 new passing unit tests
  and +1 new integration test that errors under the same pre-existing pollution.
- Each subdir passes green when run alone (unit/cascade 96, foreign_keys 28).
- The full suite in natural order (the plan's prescribed Task 9 gate) is fully green.

No gap attributable to this change.

---
_Verified: 2026-07-16_
_Verifier: Claude (gsd-verifier)_
