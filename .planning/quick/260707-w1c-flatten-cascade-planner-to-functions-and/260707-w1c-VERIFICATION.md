---
phase: quick-260707-w1c
verified: 2026-07-08T00:00:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
---

# Quick Task: Flatten cascade planner to functions and dataclasses — Verification Report

**Task Goal:** Behavior-preserving refactor of the cascade planner — dissolve the `CascadePlanner` class into module-level functions, drop dead `field_attr`/`global_attr` parameterization, simplify the edge classifier to single-hop static form; replace plan-table dicts with frozen dataclasses `CascadeEdge`/`CascadePlanEntry`; make `_inject_cascade_plan` models-only (asdict at the Lua boundary); move `CascadeTargetTtlMissingError` import to module top while keeping the justified cycle-breaker import. Lua plan table and apply.lua logic must stay byte-identical (comment-only edits allowed).

**Verified:** 2026-07-08
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `rapyer.cascade.planner` has no `CascadePlanner` class; `build_cascade_plan`/`validate_cascade_ttl_targets`/`_classify_edge` are plain module-level functions | ✓ VERIFIED | Read full file `rapyer/cascade/planner.py` — no class definition exists besides the two frozen dataclasses; all logic functions are top-level `def`. `grep -rn "CascadePlanner" rapyer/ tests/` returns zero matches. |
| 2 | `build_cascade_plan(...)` returns `dict[str, CascadePlanEntry]`, each entry's `fks` a `list[CascadeEdge]` — not raw dicts | ✓ VERIFIED | `planner.py:196-216`: `plan[model_cls.__name__] = CascadePlanEntry(ttl=..., special_suffixes=..., fks=fks)`; `fks` built via `_static_walk_fk_edges` appending `CascadeEdge(...)` instances. Confirmed at runtime: `build_cascade_plan([CascadeAuthor])['CascadeAuthor']` is a `CascadePlanEntry` instance. |
| 3 | `_inject_cascade_plan` accepts only `CascadePlanEntry` entries — no plain-dict back door — and always converts via `dataclasses.asdict` before `_lua_literal` | ✓ VERIFIED | `rapyer/scripts/registry.py:119-135`: signature `plan: dict[str, "CascadePlanEntry"]`, body unconditionally does `_lua_literal(asdict(entry))` for every entry — no `is_dataclass` branch, no dict-literal path. |
| 4 | Lua's baked `CASCADE_PLAN` table byte-identical to before, proven by injection + apply tests rewritten to build `CascadePlanEntry`/`CascadeEdge` instead of hand-built dicts | ✓ VERIFIED | `tests/unit/cascade/test_cascade_plan_injection.py` fixtures all construct `CascadePlanEntry`/`CascadeEdge`; assertions unchanged (same generated Lua string checks). All pass. |
| 5 | `rapyer.cascade` no longer exports `CascadePlanner` | ✓ VERIFIED | `rapyer/cascade/__init__.py` exports only `CascadeSpec`, `CascadeTTL`, `TTLCascadeMode`. Runtime check: `assert not hasattr(rapyer.cascade, 'CascadePlanner')` passes. |
| 6 | `planner.py` has exactly one in-function import (`from rapyer.base import AtomicRedisModel` inside `_unwrap_nested_model_cls`); every other import is at module top | ✓ VERIFIED | Module-top imports include `dataclass`, `TYPE_CHECKING`/`Any`/`get_origin`, `CascadeTargetTtlMissingError` (module-top, not inline anymore), `RelationalFieldType`, `strip_optional`, `resolve_generic_args`/`safe_issubclass`, plus a `TYPE_CHECKING`-guarded `AtomicRedisModel` import (structural, not a runtime in-function import). The only true in-function import is line 95 inside `_unwrap_nested_model_cls`, with its cycle-breaker comment intact. |
| 7 | All existing unit and real-Redis integration cascade tests pass, with dict-subscript → attribute access and dict-literal → dataclass-construction rewrites | ✓ VERIFIED | `python -m pytest tests/unit -q` → 800 passed (matches pre-refactor baseline). `python -m pytest tests/integration/foreign_keys/test_cascade_ttl_apply.py -q` → 3 passed against real Redis Stack (localhost:6370). |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `rapyer/cascade/planner.py` | `CascadeEdge`/`CascadePlanEntry` frozen dataclasses + module functions; no `CascadePlanner` class | ✓ VERIFIED | Both dataclasses present (`@dataclass(frozen=True)`), `_unwrap_relational_target`, `_classify_edge`, `_resolve_target_cls`, `_unwrap_nested_model_cls`, `_static_walk_fk_edges`, `_static_walk_special_suffixes`, `build_cascade_plan`, `validate_cascade_ttl_targets` all module-level. |
| `rapyer/cascade/__init__.py` | Public exports without `CascadePlanner` | ✓ VERIFIED | `__all__ = ["CascadeSpec", "CascadeTTL", "TTLCascadeMode"]`. |
| `rapyer/scripts/registry.py` | `_inject_cascade_plan` converts every entry via `dataclasses.asdict` — models-only | ✓ VERIFIED | Contains `asdict(entry)` at line 132; `TYPE_CHECKING`-only import of `CascadePlanEntry`. |
| `tests/unit/cascade/test_cascade_plan_table.py` | Attribute-access assertions, including `test_shape1_disabled_field_produces_no_edge` | ✓ VERIFIED | All 12 tests use `.fks`, `.path`, `.target`, etc.; `test_shape1_disabled_field_produces_no_edge` uses `plan['CascadeBookDirect'].fks == []`. |
| `tests/unit/cascade/test_cascade_ttl_required_validation.py` | `_plan()` helper builds `CascadePlanEntry`/`CascadeEdge` | ✓ VERIFIED | Helper and all three inline plan-builders construct dataclasses per plan spec. |
| `tests/unit/cascade/test_cascade_plan_injection.py` | Hand-built fixtures use dataclasses; same generated Lua string assertions | ✓ VERIFIED | All three plan-dict fixtures rewritten to `CascadePlanEntry`/`CascadeEdge`; assertions unchanged. |
| `rapyer/scripts/lua/cascade/apply.lua` | Comment-only changes vs prior commit | ✓ VERIFIED | `git diff` against previous commit shows exactly the three specified comment blocks changed; zero executable-line diffs. |
| `tests/models/cascade_types.py` | Stale `CascadePlanner` comment references fixed | ✓ VERIFIED | `grep -n "CascadePlanner"` returns zero matches; section-header comment now reads "cascade-edge-classification fixtures". |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `rapyer/scripts/registry.py` | `rapyer/cascade/planner.py` | `TYPE_CHECKING` import of `CascadePlanEntry` + `asdict` conversion | ✓ WIRED | `if TYPE_CHECKING: from rapyer.cascade.planner import CascadePlanEntry`; `_inject_cascade_plan` uses `asdict(entry)` unconditionally. |
| `rapyer/init.py` | `rapyer/cascade/planner.py` | unchanged call sites `build_cascade_plan(REDIS_MODELS)` / `validate_cascade_ttl_targets(...)` | ✓ WIRED | `rapyer/scripts/registry.py:145,150` calls `build_cascade_plan(REDIS_MODELS)` inside `register_scripts`; confirmed via passing integration test that exercises full `init_rapyer()` → script registration path. |
| `tests/unit/cascade/test_cascade_plan_table.py` | `rapyer/cascade/planner.py` | `from rapyer.cascade.planner import CascadePlanEntry, CascadeEdge, build_cascade_plan` | ✓ WIRED | Import present at top of test file; used throughout. |

### Anti-Patterns Found

None. `grep -rn "CascadePlanner\|field_attr\|global_attr\|is_dataclass" rapyer/ tests/` returns only one unrelated pre-existing hit (`tests/unit/cascade/test_cascade_ttl_config.py:31`, `dataclasses.is_dataclass(cascade_ttl)` — checking `CascadeTTL` is a frozen dataclass, unrelated to the removed injection-boundary `is_dataclass` branch this task targeted).

No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers found in any of the six modified files.

### Requirements Coverage

No `requirements:` IDs declared in this plan's frontmatter (`requirements: []`). N/A.

### Human Verification Required

None. All truths verifiable via static grep/read plus automated test execution.

## Commands Run

```
python -m pytest tests/unit -q                                          → 800 passed
python -m pytest tests/integration/foreign_keys/test_cascade_ttl_apply.py -q → 3 passed (real Redis Stack, localhost:6370)
python -c "import rapyer"                                                → succeeds
black --check <7 touched files>                                          → clean
ruff check <7 touched files>                                             → clean
grep -rn "CascadePlanner\|field_attr\|global_attr\|is_dataclass" rapyer/ tests/  → only unrelated pre-existing hit
git diff HEAD~1 -- rapyer/scripts/lua/cascade/apply.lua                  → confirms comment-only diff (3 blocks)
```

---

_Verified: 2026-07-08_
_Verifier: Claude (gsd-verifier)_
