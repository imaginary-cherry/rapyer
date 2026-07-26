---
phase: quick-260708-lku
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - rapyer/base.py
  - rapyer/cascade/planner.py
  - tests/unit/cascade/test_cascade_classification.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "AtomicRedisModel no longer defines or populates a class-level _cascade_ttl_fields dict, nor the inherit-then-overwrite workaround in __init_subclass__"
    - "The cascade planner classifies a field's explicit CascadeTTL override by reading it directly off pydantic's own per-field FieldInfo.metadata, for all three D-06 shapes (direct FK, collection-of-FK, nested-submodel), with identical enabled/depth/override precedence as before (field spec > Meta.cascade_ttl global blanket > disabled)"
    - "Shape-3 (nested inline submodel) classification works via ordinary pydantic field/metadata inheritance from the wrapped class into its dynamically-created wrapper subclass -- no custom class-attribute copying is needed to make it work"
    - "Full unit and integration suites pass unchanged at their pre-refactor baselines (819 unit, 1593 passed/205 skipped integration), run as two separate uv run pytest invocations"
  artifacts:
    - path: "rapyer/base.py"
      provides: "__init_subclass__ with the _cascade_ttl_fields ClassVar, its inherit-then-overwrite copy, and its per-field extract_annotation(..., CascadeTTL) population removed"
    - path: "rapyer/cascade/planner.py"
      provides: "_field_cascade_spec(model_cls, field_name) helper reading model_cls.model_fields[field_name].metadata for a CascadeTTL instance; _classify_edge rewritten to call it instead of getattr(model_cls, \"_cascade_ttl_fields\", {})"
      contains: "def _field_cascade_spec"
    - path: "tests/unit/cascade/test_cascade_classification.py"
      provides: "Shape-1/2/3 and no-marker classification assertions rewritten against build_cascade_plan(...) output (or deleted where fully duplicated by tests/unit/cascade/test_cascade_plan_table.py) instead of the removed _cascade_ttl_fields attribute"
  key_links:
    - from: "rapyer/cascade/planner.py _classify_edge"
      to: "pydantic FieldInfo.metadata"
      via: "model_cls.model_fields[field_name].metadata scanned for isinstance(meta, CascadeTTL)"
      pattern: "model_fields\\[field_name\\]\\.metadata"
    - from: "rapyer/base.py __init_subclass__"
      to: "rapyer/cascade/planner.py _field_cascade_spec"
      via: "no direct link -- base.py stops extracting/storing CascadeTTL entirely; the annotation's Annotated metadata survives untouched into pydantic's model_fields, which planner.py reads independently"
      pattern: "extract_annotation\\(annotation, CascadeTTL\\)"
---

<objective>
Eliminate `AtomicRedisModel._cascade_ttl_fields` (the class-level `dict[str, CascadeTTL]` built and inherit-then-overwritten in `__init_subclass__`) and have the cascade planner read each field's explicit `CascadeTTL` override directly off the field itself, mirroring how `safe_load` already flows from annotation to behavior -- but landing on a different, more direct mechanism once the actual annotation-conversion pipeline was traced end to end (see Resolved Risk below).

**Resolved risk (empirically verified, see traces below):** `ForeignKey`/`Reference` fields are a `RelationalFieldType`, and `rapyer.utils.annotation.replace_to_redis_types_in_annotation` explicitly exempts `RelationalFieldType` annotations from conversion (`rapyer/utils/annotation.py:36-37`, "Relational field is not dynamically created, it stays simple field") -- so shape-1 FK fields never get a generated per-field subclass the way `RedisInt`/`RedisList`/etc. do via `RedisConverter.convert_flat_type`/`covert_generic_type`. There is nothing to bake `safe_load`-style onto for shape 1. However, `replace_to_redis_types_in_annotation`'s `Annotated` branch (`rapyer/utils/annotation.py:52-62`) always reconstructs `Annotated[new_type, *original_metadata]` regardless of whether `new_type` changed -- so an explicit `Annotated[Reference[X], CascadeTTL(...)]` marker survives byte-identical into `cls.__annotations__`, and from there into pydantic's `FieldInfo.metadata` for that field (confirmed empirically with a standalone pydantic 2.12 reproduction: a direct field's `model_fields['author'].metadata == [CascadeTTL(...)]`, and a `list[...]`-wrapped collection field behaves identically). For shape 3 (nested inline submodel), `convert_flat_type`'s `AtomicRedisModel` branch (`rapyer/types/convert.py:65-70`) wraps the nested class in `type(name, (NestedCls,), dict(__doc__=...))` -- confirmed empirically that this wrapper's own `__dict__` has NO `__annotations__` of its own (so `AtomicRedisModel.__init_subclass__`'s raw-annotation loop sees nothing new for it, which is exactly why the old inherit-then-overwrite `_cascade_ttl_fields` copy existed) -- but pydantic's own `model_fields` machinery DOES correctly inherit the wrapped class's `FieldInfo` (metadata included) onto the wrapper subclass via ordinary Python/pydantic subclassing (confirmed empirically: `Wrapper.model_fields['fk'].metadata` on a dynamically `type()`-created wrapper subclass equals the wrapped class's own metadata for that field). So reading `model_cls.model_fields[field_name].metadata` is a single, uniform accessor that already works correctly for all three D-06 shapes with zero changes needed to `rapyer/types/convert.py` or `RedisConverter` -- this is a narrower, more direct fix than mirroring `safe_load`'s bake-into-generated-subclass mechanism, and it is what actually eliminates the class-level dict and its inherit-workaround.

Purpose: Remove class-level bookkeeping (`_cascade_ttl_fields` + its inherit-then-overwrite copy) that duplicates information pydantic's own per-field metadata already carries, so the marker genuinely lives "on the field" instead of in a hand-maintained parallel dict on `AtomicRedisModel`.
Output: `rapyer/base.py` with `_cascade_ttl_fields` and its population/inherit logic deleted; `rapyer/cascade/planner.py` with a new `_field_cascade_spec` helper and `_classify_edge` reading through it; `tests/unit/cascade/test_cascade_classification.py` updated to assert through the planner's public `build_cascade_plan` output instead of the removed attribute.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md

<interfaces>
New contract Task 1 introduces in rapyer/cascade/planner.py -- Task 2's test rewrite does not call this directly (it exercises build_cascade_plan, the existing public entry point) but must know it exists and why _cascade_ttl_fields is gone:

def _field_cascade_spec(model_cls: Any, field_name: str) -> CascadeTTL | None
  -- returns the CascadeTTL instance found in model_cls.model_fields[field_name].metadata, or None if absent. Requires "from rapyer.cascade.ttl import CascadeTTL" at planner.py's top (module-internal import, same package -- no cycle: rapyer/cascade/__init__.py only imports spec.py and ttl.py, never planner.py).

_classify_edge(model_cls, field_name) -> tuple[bool, int | None, bool] keeps its exact existing signature and precedence (field spec else Meta.cascade_ttl global blanket else disabled; override=True whenever an explicit field spec matched, whether enabled or disabled) -- only its data source changes, from "getattr(model_cls, '_cascade_ttl_fields', {}).get(field_name)" to "_field_cascade_spec(model_cls, field_name)".

Current (pre-refactor) call site being replaced, for reference -- rapyer/cascade/planner.py:67 currently reads "field_specs = getattr(model_cls, '_cascade_ttl_fields', {}); field_spec = field_specs.get(field_name)". rapyer/base.py:176 currently declares "_cascade_ttl_fields: ClassVar[dict[str, 'CascadeTTL']] = {}"; base.py:363-370 copies it (inherit-then-overwrite) at the top of __init_subclass__; base.py:376-378 populates it per field via "cascade_spec = extract_annotation(annotation, CascadeTTL); if cascade_spec is not None: cls._cascade_ttl_fields[field_name] = cascade_spec" inside the same raw-annotation loop that already handles KeyAnnotation/SafeLoadAnnotation. All three of these go away; nothing replaces them in base.py -- the marker is left to ride along in pydantic's own model_fields metadata, which base.py never needs to touch.

rapyer.utils.annotation.extract_annotation (rapyer/utils/annotation.py:116-123) is NOT removed -- it stays as a general-purpose reusable annotation utility with its own dedicated tests (tests/unit/cascade/test_extract_annotation.py, unaffected by this plan). It simply loses its only call site inside rapyer/ (base.py:376); do not repurpose it inside _field_cascade_spec since it operates on an Annotated TYPE (get_origin(field) is Annotated), not on a FieldInfo.metadata LIST -- a plain "next(m for m in metadata if isinstance(m, CascadeTTL))" scan is the correct, simpler primitive for the new accessor.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Move CascadeTTL classification off the class-level dict onto pydantic field metadata</name>
  <files>rapyer/base.py, rapyer/cascade/planner.py</files>
  <action>
    In rapyer/base.py:

    1. Remove the `_cascade_ttl_fields: ClassVar[dict[str, "CascadeTTL"]] = {}` class attribute declaration (currently at line 176, between `_contain_fk` and `_has_cascade`). Leave `_has_cascade: ClassVar[bool] = False` and every other ClassVar untouched.

    2. In `__init_subclass__`'s first loop (the one currently handling `KeyAnnotation`/`SafeLoadAnnotation`/cascade extraction over `cls.__annotations__.items()`), delete: the multi-line comment explaining the inherit-then-overwrite rationale, the `cls._cascade_ttl_fields = dict(getattr(cls, "_cascade_ttl_fields", {}))` line that precedes the loop, and inside the loop body the `cascade_spec = extract_annotation(annotation, CascadeTTL)` / `if cascade_spec is not None: cls._cascade_ttl_fields[field_name] = cascade_spec` block. Leave the `KeyAnnotation`/`SafeLoadAnnotation` handling in that loop completely untouched -- it is unrelated and must keep working exactly as before.

    3. Remove the now-unused `from rapyer.cascade import CascadeTTL` top-level import and remove `extract_annotation` from the `from rapyer.utils.annotation import (...)` import block (keep `DYNAMIC_CLASS_DOC`, `annotation_origin`, `field_with_flag`, `has_annotation`, `replace_to_redis_types_in_annotation`, `strip_optional` -- everything else in that block is still used elsewhere in the file). Confirm via grep that neither `CascadeTTL` nor `extract_annotation` is referenced anywhere else in base.py before removing the imports.

    In rapyer/cascade/planner.py:

    4. Add `from rapyer.cascade.ttl import CascadeTTL` to the top-level imports (module-internal sibling import within the `rapyer.cascade` package -- not `from rapyer.cascade import CascadeTTL`, to avoid any ambiguity about package `__init__` load order, matching how `rapyer/cascade/ttl.py` itself imports directly from `rapyer.cascade.spec`).

    5. Add a new module-level function `_field_cascade_spec(model_cls: Any, field_name: str) -> CascadeTTL | None` placed immediately before `_classify_edge`. Body: fetch `field_info = model_cls.model_fields[field_name]` (direct subscript, matching the existing no-`.get`-guard style already used by `_resolve_target_cls`'s `model_cls.model_fields[field_name].annotation` -- `field_name` always comes from `_relational_field_names`/`_contain_fk`, both real field-name sets, so the key always exists), then return the first entry of `field_info.metadata` that `isinstance(..., CascadeTTL)`, or `None` if none matches. Give it a short docstring stating it reads the explicit per-field marker straight off pydantic's own `FieldInfo.metadata` (survives Rapyer's redis-type conversion for every D-06 shape -- see this plan's objective for the empirical trace) instead of a class-level lookup table.

    6. Rewrite `_classify_edge`'s body to call `field_spec = _field_cascade_spec(model_cls, field_name)` instead of `field_specs = getattr(model_cls, "_cascade_ttl_fields", {}); field_spec = field_specs.get(field_name)`. Keep every other line -- the enabled/depth/override precedence, the docstring, the return tuple shape -- byte-identical.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && python -c "from rapyer.cascade.planner import build_cascade_plan; from tests.models.cascade_types import CascadeBookDirect, CascadeBookCollection, CascadeBookNested, CascadeProfile, CascadeAuthor, CascadeBlanketRoot, CascadeBlanketLeaf; plan = build_cascade_plan([CascadeBookDirect, CascadeAuthor]); assert plan['CascadeBookDirect'].fks == []; plan = build_cascade_plan([CascadeBookCollection, CascadeAuthor]); edges = plan['CascadeBookCollection'].fks; assert len(edges) == 1 and edges[0].collection is True and edges[0].target == 'CascadeAuthor'; plan = build_cascade_plan([CascadeBookNested, CascadeProfile, CascadeAuthor]); edges = plan['CascadeBookNested'].fks; assert len(edges) == 1 and edges[0].path == '\$.profile.mentor' and edges[0].target == 'CascadeAuthor'; plan = build_cascade_plan([CascadeBlanketRoot, CascadeBlanketLeaf]); edge = plan['CascadeBlanketRoot'].fks[0]; assert edge.depth == 2 and edge.override is False; assert not hasattr(CascadeBookDirect, '_cascade_ttl_fields'); print('classification-preserved')" && ! grep -n "_cascade_ttl_fields" rapyer/base.py rapyer/cascade/planner.py</automated>
  </verify>
  <done>rapyer/base.py no longer declares, copies, or populates _cascade_ttl_fields; rapyer/cascade/planner.py classifies shape-1/2/3 edges identically to before (disabled/enabled, depth, collection, override, blanket-global precedence) by reading model_cls.model_fields[field_name].metadata through the new _field_cascade_spec helper.</done>
</task>

<task type="auto">
  <name>Task 2: Update the whitebox classification test to the new accessor and run full regression</name>
  <files>tests/unit/cascade/test_cascade_classification.py</files>
  <action>
    tests/unit/cascade/test_cascade_classification.py currently asserts directly on the removed `Model._cascade_ttl_fields` attribute for every scenario. Cross-referencing tests/unit/cascade/test_cascade_plan_table.py (already exercises the SAME fixture models through the public `build_cascade_plan` API) shows four of its assertions are exact behavioral duplicates there; rewrite the file as follows -- this is a flagged, reasoned test-file change (the internal representation the file probed is exactly what this refactor removes), not a silent edit, and it removes zero net test scenarios:

    - Delete `test_direct_fk_field_records_exact_cascade_ttl_instance` (CascadeBookDirect shape-1-disabled case) -- fully duplicated by test_cascade_plan_table.py::test_shape1_disabled_field_produces_no_edge (same model, same assertion in substance: no edge produced).
    - Delete `test_collection_fk_field_records_cascade_ttl_on_the_collection_field` (CascadeBookCollection shape-2 case) -- fully duplicated by test_cascade_plan_table.py::test_shape2_collection_of_fk_produces_exactly_one_edge_marked_collection.
    - Delete `test_nested_submodel_records_marker_on_the_nested_class_not_the_outer_one` (CascadeProfile/CascadeBookNested shape-3 case) -- fully duplicated by test_cascade_plan_table.py::test_shape3_nested_submodel_edge_lands_on_holder_and_hides_nested_class.
    - Delete `test_cascade_author_leaf_model_has_no_cascade_ttl_fields` (CascadeAuthor leaf case) -- fully duplicated by test_cascade_plan_table.py::test_every_model_gets_exactly_one_entry_even_a_plain_leaf (asserts fks=[] for the same class).
    - Rewrite `test_plain_fk_field_without_cascade_ttl_has_empty_cascade_ttl_fields` (CascadeBookPlain, no marker anywhere, not duplicated elsewhere) to call `build_cascade_plan([CascadeBookPlain, CascadeAuthor])` and assert `plan["CascadeBookPlain"].fks == []`; rename it to `test_plain_fk_field_without_cascade_ttl_produces_no_edge`. Add `from rapyer.cascade.planner import build_cascade_plan` to the imports; drop the now-unused `from rapyer.cascade import CascadeTTL` import once nothing else in the file references `CascadeTTL` directly after these deletions (neither `test_plain_fk_field_classification_is_unaffected` nor `test_existing_fk_book_classification_remains_byte_identical` reference it).
    - Keep `test_plain_fk_field_classification_is_unaffected` (asserts `CascadeBookPlain._relational_field_names == {"author"}`) completely untouched -- unrelated attribute, not part of this refactor.
    - In `test_existing_fk_book_classification_remains_byte_identical`, drop the `assert FkBook._cascade_ttl_fields == {}` line (the attribute no longer exists) and replace it with `assert build_cascade_plan([FkBook]).get("FkBook").fks == []` (FkBook carries no CascadeTTL marker and no Meta.cascade_ttl blanket, so it must still produce zero cascade edges -- proving COMPAT-02 still holds under the new accessor). Keep the `_relational_field_names`/`_contain_fk` assertions in that test exactly as they are.

    After the rewrite, the file should contain exactly three tests: `test_plain_fk_field_without_cascade_ttl_produces_no_edge`, `test_plain_fk_field_classification_is_unaffected`, `test_existing_fk_book_classification_remains_byte_identical`. Remove any now-unused fixture imports from `tests.models.cascade_types` (`CascadeBookCollection`, `CascadeBookDirect`, `CascadeBookNested`, `CascadeProfile` all become unused after the deletions above -- keep only `CascadeAuthor`, `CascadeBookPlain`).

    Then run the full regression exactly as specified in this quick task's constraints, as two SEPARATE invocations (per CONCERNS.md fakeredis/real-Redis divergence -- never combine them into one pytest run):
    - `uv run pytest tests/unit/ -q` -- must show 819 passed (net test count unchanged: 4 tests deleted, 1 renamed/rewritten in place, 0 net change).
    - `uv run pytest tests/integration/ -q` -- must show 1593 passed, 205 skipped, against real Redis Stack at localhost:6370.
    - `black --check --diff rapyer/base.py rapyer/cascade/planner.py tests/unit/cascade/test_cascade_classification.py` and `ruff check rapyer/base.py rapyer/cascade/planner.py tests/unit/cascade/test_cascade_classification.py` -- both clean.

    If either suite's pass count differs from the stated baseline, or any OTHER test file (outside test_cascade_classification.py) needs an edit to pass, STOP and report the discrepancy instead of silently editing further tests -- that would signal an actual behavior drift, not the expected whitebox-test update this task performs.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && uv run pytest tests/unit/cascade/test_cascade_classification.py -q && uv run pytest tests/unit/ -q && uv run pytest tests/integration/ -q && black --check --diff rapyer/base.py rapyer/cascade/planner.py tests/unit/cascade/test_cascade_classification.py && ruff check rapyer/base.py rapyer/cascade/planner.py tests/unit/cascade/test_cascade_classification.py && ! grep -rn "_cascade_ttl_fields" rapyer/ tests/</automated>
  </verify>
  <done>tests/unit/cascade/test_cascade_classification.py asserts through build_cascade_plan instead of the removed _cascade_ttl_fields attribute, with zero net loss of test coverage; tests/unit/ passes at 819, tests/integration/ passes at 1593 passed/205 skipped against real Redis Stack; black and ruff are clean on all three touched files; _cascade_ttl_fields has zero remaining references anywhere in rapyer/ or tests/.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|--------------|
| Field-declared CascadeTTL marker -> pydantic FieldInfo.metadata -> cascade planner | The `CascadeTTL` instance is authored by the application developer directly in their own model's field annotation (`Annotated[Reference[X], CascadeTTL(...)]`); it is never derived from request-time, network, or otherwise attacker-controlled input at any point in this refactor's data flow. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|------------------|
| T-quick-01 | Tampering | rapyer/base.py __init_subclass__ + rapyer/cascade/planner.py _classify_edge | accept | Pure internal refactor of class-definition-time/import-time Python that only ever consumes developer-authored model annotations and pydantic's own field metadata -- no external or request-time input crosses this code at any point; behavior parity is proven by the full existing unit + real-Redis integration suite staying green at their pre-refactor baselines. |
| T-quick-02 | Repudiation (silent behavior drift) | tests/unit/cascade/test_cascade_classification.py rewrite | mitigate | Every deletion/rewrite in this test file is explicitly enumerated and justified in Task 2's action against its exact behavioral duplicate in tests/unit/cascade/test_cascade_plan_table.py; the plan requires stopping and reporting rather than silently editing if any OTHER test file needs a change, or if either suite's pass count deviates from its stated baseline. |

No npm/pip/cargo package installs are introduced by this plan; the package-legitimacy gate does not apply.
</threat_model>

<verification>
1. `python -c "import rapyer"` succeeds with no import errors (proves the base.py import removals and planner.py's new `rapyer.cascade.ttl` import introduce no circular import).
2. `uv run pytest tests/unit/ -q` -- 819 passed, matching the pre-refactor baseline exactly.
3. `uv run pytest tests/integration/ -q` -- 1593 passed, 205 skipped, run separately against real Redis Stack (localhost:6370), matching the pre-refactor baseline exactly.
4. `black --check --diff` and `ruff check` clean on rapyer/base.py, rapyer/cascade/planner.py, tests/unit/cascade/test_cascade_classification.py.
5. `grep -rn "_cascade_ttl_fields" rapyer/ tests/` -- zero matches anywhere in the repo.
</verification>

<success_criteria>
- `AtomicRedisModel` no longer declares, copies, or populates `_cascade_ttl_fields`; the inherit-then-overwrite workaround comment and code are gone from `__init_subclass__`.
- `rapyer/cascade/planner.py`'s `_classify_edge` reads each field's explicit `CascadeTTL` override via a new `_field_cascade_spec(model_cls, field_name)` helper that scans `model_cls.model_fields[field_name].metadata`, with identical enabled/depth/override precedence as before for all three D-06 shapes.
- `tests/unit/cascade/test_cascade_classification.py` no longer references the removed attribute; its scenarios are preserved either via deletion (exact duplicate already covered by `test_cascade_plan_table.py`) or rewrite against `build_cascade_plan`'s public output.
- `uv run pytest tests/unit/ -q` (819 passed) and `uv run pytest tests/integration/ -q` (1593 passed, 205 skipped, real Redis) both pass, run as separate invocations.
- `black --check` and `ruff check` are clean on every touched file; `python -c "import rapyer"` succeeds.
- Zero repo-wide references to `_cascade_ttl_fields`.
</success_criteria>

<output>
Create `.planning/quick/260708-lku-move-per-field-cascadettl-config-onto-th/260708-lku-SUMMARY.md` when done
</output>
