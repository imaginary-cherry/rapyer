# Quick Task 260708-lku: Remove redundant per-field CascadeTTL cache Summary

Eliminated `AtomicRedisModel._cascade_ttl_fields` (a class-level dict cache that duplicated config pydantic already stores in `FieldInfo.metadata`) by reading the `CascadeTTL` marker directly off `model_fields[field_name].metadata` in the cascade planner.

## What Changed

- `rapyer/cascade/planner.py`: added `_field_cascade_spec(model_cls, field_name) -> CascadeTTL | None`, which iterates `model_cls.model_fields[field_name].metadata` and returns the matched `CascadeTTL` instance (or `None`). Rewired `_classify_edge` to call this helper instead of `getattr(model_cls, "_cascade_ttl_fields", {})`. The `(enabled, depth, override)` precedence and return contract (field spec → else `Meta.cascade_ttl` global blanket → else disabled; `override=True` iff an explicit field spec exists) is preserved exactly.
- `rapyer/base.py`: deleted the `_cascade_ttl_fields: ClassVar[dict[str, "CascadeTTL"]] = {}` class attribute, its populate loop in `__init_subclass__`, and the inherit-then-overwrite line + explanatory comment that existed solely to carry the marker onto dynamically-created nested-submodel wrapper subclasses (whose `__annotations__` is empty). Removed the now-unused `CascadeTTL` and `extract_annotation` imports.
- `tests/unit/cascade/test_cascade_classification.py`: updated all assertions from `Model._cascade_ttl_fields == {...}` to `_field_cascade_spec(Model, "field_name") == CascadeTTL(...)` / `is None`, preserving the exact same shape-1/2/3 classification coverage this whitebox test existed to provide. Not deleted as a duplicate — it asserts at the single-field-metadata granularity, distinct from `test_cascade_plan_table.py`'s full-edge/plan-output assertions.

## Why This Is Safe (verified facts)

1. FK fields are exempted from redis-type conversion (`rapyer/utils/annotation.py:36-37`), so shape-1/2 FK fields never get a generated per-field subclass — `rapyer/types/convert.py` was untouched, as instructed.
2. `CascadeTTL` survives byte-identical into `model_cls.model_fields[field_name].metadata` for shape 1 (single FK) and shape 2 (list[ForeignKey[...]]) because `replace_to_redis_types_in_annotation` preserves original `Annotated` metadata.
3. For shape 3 (nested inline sub-model), pydantic's own field inheritance carries `FieldInfo.metadata` from the wrapped class onto the dynamically-created wrapper class for free — confirmed empirically (`CascadeBookNested.model_fields["profile"].metadata == []`, while `CascadeProfile.model_fields["mentor"].metadata == [CascadeTTL(...)]`, and the planner recurses into the nested class via `_static_walk_fk_edges`, so the old inherit-then-overwrite workaround was unnecessary).

## Deviations from Plan

None — plan executed exactly as written. `_has_cascade`, `Meta.cascade_ttl`, `apply.lua`, `run_sha`, and the no-config path were left untouched per instructions.

## Verification

- `grep -rn "\._cascade_ttl_fields\b\|_cascade_ttl_fields =" rapyer/ tests/` → **zero hits** (confirms the dict/attribute is fully gone; the only textual matches left are test *function names* containing the substring, e.g. `test_cascade_author_leaf_model_has_no_cascade_ttl_fields`, which are not attribute references).
- `uv run pytest tests/unit/ -q` → **819 passed** (matches baseline exactly, no delta).
- `uv run pytest tests/integration/ -q` (separate invocation, real Redis Stack at `localhost:6370`) → **1593 passed, 205 skipped** (matches baseline exactly).
- `uv run pytest tests/unit/cascade/ -q` → **80 passed** (D-06 shapes 1/2/3 all pass under the new accessor).
- `uv run pytest tests/integration/foreign_keys/ -q` → **21 passed**.
- `uv run black --check` and `uv run ruff check` on every touched file (`rapyer/base.py`, `rapyer/cascade/planner.py`, `tests/unit/cascade/test_cascade_classification.py`) → all clean, no changes needed.
- No cascade BEHAVIOR test was edited — only the whitebox `test_cascade_classification.py`, which asserts on internal per-field spec extraction, not on cascade traversal/apply behavior. All cascade behavior tests (`test_cascade_plan_table.py`, `test_cascade_apply_lua.py`, `test_refresh_ttl_cascade_branch.py`, `test_init_rapyer_cascade_ttl.py`) were left untouched and pass unchanged.

## Environment Note (unrelated to this task)

The worktree's `.venv` initially had no dev/test dependencies installed (`uv sync --locked --group dev` alone only installs `black`/`mypy`/`ruff`; `pytest`/`pytest-asyncio`/`fakeredis`/etc. live under `[project.optional-dependencies].test`, not a dependency-group). Reproduced the resulting `ModuleNotFoundError: No module named 'rapyer.actions'` on a pristine (unmodified) checkout of the touched files to confirm it was pre-existing environment state, not caused by this refactor. Ran `uv sync --locked --extra test --group dev` to install the missing test extras before verification; this is an environment-setup action only, no lockfile or pyproject changes were made or committed.

## Commits

- `81326e9` refactor(quick-260708-lku): add pydantic-metadata cascade spec accessor
- `2af5eea` refactor(quick-260708-lku): remove redundant _cascade_ttl_fields cache

## Self-Check

- `rapyer/cascade/planner.py` contains `_field_cascade_spec` — FOUND
- `rapyer/base.py` no longer contains `_cascade_ttl_fields` — CONFIRMED (grep zero hits)
- `tests/unit/cascade/test_cascade_classification.py` uses `_field_cascade_spec` — FOUND
- Commit `81326e9` exists in `git log` — FOUND
- Commit `2af5eea` exists in `git log` — FOUND

## Self-Check: PASSED
