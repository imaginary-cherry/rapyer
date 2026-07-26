---
phase: quick-260707-w1c
plan: 01
subsystem: cascade
tags: [cascade, refactor, dataclass, lua-injection]
dependency-graph:
  requires: []
  provides:
    - rapyer.cascade.planner.CascadeEdge
    - rapyer.cascade.planner.CascadePlanEntry
    - rapyer.cascade.planner.build_cascade_plan (flat function, dataclass shape)
    - rapyer.cascade.planner.validate_cascade_ttl_targets (flat function, dataclass shape)
  affects:
    - rapyer/scripts/registry.py (_inject_cascade_plan models-only bridge)
tech-stack:
  added: []
  patterns:
    - "dataclasses.asdict as the sole bridge from typed plan dataclasses to the Lua-literal serializer"
key-files:
  created: []
  modified:
    - rapyer/cascade/planner.py
    - rapyer/cascade/__init__.py
    - rapyer/scripts/registry.py
    - rapyer/scripts/lua/cascade/apply.lua
    - tests/unit/cascade/test_cascade_plan_table.py
    - tests/unit/cascade/test_cascade_ttl_required_validation.py
    - tests/unit/cascade/test_cascade_plan_injection.py
    - tests/models/cascade_types.py
decisions:
  - "CascadeEdge/CascadePlanEntry are frozen dataclasses replacing the raw-dict plan-table shape; equality is field-by-field so dict-literal-style test comparisons still work unchanged."
  - "_inject_cascade_plan is models-only: no dual dict/dataclass accept path, always dataclasses.asdict(entry) before the unchanged _lua_literal serializer."
  - "_classify_edge (renamed from _next_hop) drops the dead established/remaining_budget decrement branches — that bookkeeping already lives exclusively in the Lua apply script's own next_hop."
metrics:
  duration: ~25min
  completed: 2026-07-07
---

# Phase quick-260707-w1c Plan 01: Flatten CascadePlanner into functions and models Summary

Dissolved the now-nearly-empty `CascadePlanner` class into plain module functions in `rapyer/cascade/planner.py`, replaced the raw-dict plan-table shape with frozen `CascadeEdge`/`CascadePlanEntry` dataclasses, and made the Lua-injection boundary (`_inject_cascade_plan`) models-only via `dataclasses.asdict`.

## What Was Built

**Task 1 — `rapyer/cascade/planner.py` flattened, dataclasses introduced** (commit `c513a54`):
- Deleted the `CascadePlanner` class entirely; its three surviving methods became module-level functions: `_classify_edge` (renamed from `_next_hop`), `_resolve_target_cls`, `_unwrap_nested_model_cls`.
- `_classify_edge` is now a pure single-hop static classifier — the dead `established`/`remaining_budget` decrement branches (never exercised in Python; the Lua script's own `next_hop` owns all runtime multi-hop budget bookkeeping) are gone, and `override` is folded directly into its return tuple `(enabled, depth, override)`.
- Added `CascadeEdge` (fields: `path`, `target`, `collection`, `recurse`, `ttl`, `special`, `override`, `depth=None`) and `CascadePlanEntry` (fields: `ttl`, `special_suffixes`, `fks`) as frozen dataclasses.
- `_static_walk_fk_edges` dropped its `planner` parameter and now calls the module functions directly, constructing `CascadeEdge` instances (always passing `depth` explicitly, since the dataclass default is `None`).
- `build_cascade_plan` / `validate_cascade_ttl_targets` now use attribute access (`entry.fks`, `edge.target`, `entry.ttl`, etc.) instead of dict subscripting, with the exact same two-pass validation structure and sorted-iteration order preserved.
- Moved `CascadeTargetTtlMissingError` import to module top (its module only imports `rapyer.errors.base`, no cycle). Added a `TYPE_CHECKING` block importing `AtomicRedisModel` for the `build_cascade_plan` forward-ref annotation; kept the one justified in-function import (`from rapyer.base import AtomicRedisModel` inside `_unwrap_nested_model_cls`) as the sole cycle-breaker.
- `rapyer/cascade/__init__.py` no longer imports or exports `CascadePlanner`.

**Task 2 — Lua-injection boundary made models-only** (commit `c8b3a81`):
- `rapyer/scripts/registry.py`: added `from dataclasses import asdict`; added a `TYPE_CHECKING`-only import of `CascadePlanEntry`; `_inject_cascade_plan` now unconditionally does `_lua_literal(asdict(entry))` for every entry — no dict back door, no `is_dataclass` branch. `_lua_literal` itself is untouched.
- `tests/unit/cascade/test_cascade_plan_injection.py`: rewrote all three hand-built plan fixtures to construct `CascadeEdge`/`CascadePlanEntry` instances; assertions unchanged (still checking the generated Lua string).
- `rapyer/scripts/lua/cascade/apply.lua`: reworded exactly three stale comments referencing the deleted `CascadePlanner._next_hop` / `atraverse` — zero logic or other-comment changes (confirmed via `git diff`, comment-only hunks).

**Task 3 — Remaining cascade unit tests updated** (commit `84c1a55`):
- `tests/unit/cascade/test_cascade_plan_table.py`: every dict-subscript assertion rewritten to attribute access on `CascadePlanEntry`/`CascadeEdge`; `test_depth_key_absent_when_unbounded_never_present_as_none` now asserts `edge.depth is None` (the field is always present; the Lua-injection layer, tested separately, is what omits the literal `depth` key); `test_build_cascade_plan_over_redis_models_never_uses_none_as_unbounded_signal` now asserts `edge.depth is None or edge.depth >= 0` for every edge.
- `tests/unit/cascade/test_cascade_ttl_required_validation.py`: `_plan()` helper and all three inline plan-dict tests rewritten to build `CascadePlanEntry`/`CascadeEdge` instances.
- `tests/models/cascade_types.py`: fixed two stale `CascadePlanner`-referencing comments (section header, `CascadeChainNode` docstring).

## Deviations from Plan

None — plan executed exactly as written. All hand-built plan/edge shapes, comment reword text, and file lists matched the plan's interfaces and per-test breakdown.

One incidental note surfaced during verification (not a deviation, informational only): the plan's verification step 5 grep (`grep -rn "CascadePlanner\|field_attr\|global_attr\|is_dataclass" rapyer/ tests/`) has one pre-existing, out-of-scope hit — `tests/unit/cascade/test_cascade_ttl_config.py:31` (`assert dataclasses.is_dataclass(cascade_ttl)`), introduced in Phase 1 (`028c358`, not in this plan's `files_modified`). It asserts `CascadeTTL` is a dataclass — unrelated to the `_inject_cascade_plan` dual-accept anti-pattern the `is_dataclass` grep term targets. Per the scope-boundary rule, left untouched; not a regression introduced by this plan (`git log` confirms it predates this quick task).

## Verification Results

```
python -m pytest tests/unit -q
800 passed, 6 warnings in ~9.5s

python -m pytest tests/integration/foreign_keys/test_cascade_ttl_apply.py -q   (real Redis)
3 passed in 0.18s

python -c "import rapyer"
OK — no import errors

black --check rapyer/cascade/planner.py rapyer/cascade/__init__.py rapyer/scripts/registry.py \
  tests/unit/cascade/test_cascade_plan_table.py tests/unit/cascade/test_cascade_ttl_required_validation.py \
  tests/unit/cascade/test_cascade_plan_injection.py tests/models/cascade_types.py
All done — 7 files unchanged

ruff check <same file list>
All checks passed!

grep -rn "CascadePlanner\|field_attr\|global_attr\|is_dataclass" rapyer/ tests/
One pre-existing, out-of-scope hit (see Deviations note above); zero hits related to this plan's scope.

grep -n "^\s+from |^\s+import " rapyer/cascade/planner.py  (AST-verified, not just line-indent grep)
Exactly one true in-function import: line 95, "from rapyer.base import AtomicRedisModel" inside
_unwrap_nested_model_cls. (Line 10 is a TYPE_CHECKING-guarded module-level import, expected per Task 1.)
```

## Self-Check: PASSED

- FOUND: rapyer/cascade/planner.py (CascadeEdge/CascadePlanEntry dataclasses, flat functions)
- FOUND: rapyer/cascade/__init__.py (no CascadePlanner export)
- FOUND: rapyer/scripts/registry.py (asdict-based models-only bridge)
- FOUND: rapyer/scripts/lua/cascade/apply.lua (reworded comments)
- FOUND: tests/unit/cascade/test_cascade_plan_table.py
- FOUND: tests/unit/cascade/test_cascade_ttl_required_validation.py
- FOUND: tests/unit/cascade/test_cascade_plan_injection.py
- FOUND: tests/models/cascade_types.py
- FOUND commit c513a54 (Task 1)
- FOUND commit c8b3a81 (Task 2)
- FOUND commit 84c1a55 (Task 3)
