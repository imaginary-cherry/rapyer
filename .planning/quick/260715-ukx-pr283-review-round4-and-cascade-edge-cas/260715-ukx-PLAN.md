---
phase: quick-260715-ukx
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - rapyer/scripts/registry.py
  - rapyer/scripts/lua/cascade/apply.lua
  - tests/integration/pipeline/test_pipeline_noscript_recovery.py
  - tests/models/cascade_types.py
  - tests/unit/cascade/conftest.py
  - tests/integration/foreign_keys/conftest.py
  - tests/unit/cascade/test_cascade_plan_table.py
  - tests/integration/foreign_keys/test_cascade_ttl_apply.py
  - tests/unit/cascade/test_cascade_apply_lua.py
  - .planning/codebase/CONCERNS.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "The 3 noscript-recovery tests only remove data-op scripts (list/dict/numeric/atomic) via SCRIPT FLUSH, then reload ONLY the cascade TTL script's SHA -- the two recovery-enabled tests still prove _apipeline's NOSCRIPT self-heal reaches the correct final state, and the recovery-disabled test still raises PersistentNoScriptError"
    - "A model with a dict[str, Reference[T]] field annotated with CascadeTTL() produces exactly one collection-marked edge in the cascade plan table, and applying the real cascade Lua script against real Redis refreshes every dict-value FK target's TTL"
    - "A node reached only through a nested-submodel (shape 3) zero-hop field, whose own onward FK sits beyond the holder's explicit depth budget, is left unrefreshed (TTL -1/-2) while every in-budget node on the same path (root, holder, mentor) is refreshed"
    - "Applying the cascade script against a root whose reached target key holds a non-JSON (WRONGTYPE) value does not raise on real Redis Stack -- the corrupt key itself still gets a positive TTL and no traversal continues past it (fakeredis 2.34.1 does not emulate WRONGTYPE on JSON.GET, so this is proven only against real Redis, per the new CONCERNS.md entry)"
    - "Full suite (REDIS_DB=0 python -m pytest tests -q -p no:randomly, real Redis Stack) stays green after every task, and black --check + ruff check stay clean on every touched file"
  artifacts:
    - path: "rapyer/scripts/registry.py"
      provides: "build_script_texts(is_fakeredis=False) -> dict[name,str] pure helper extracted from register_scripts (behavior-preserving)"
      contains: "def build_script_texts"
    - path: "rapyer/scripts/lua/cascade/apply.lua"
      provides: "read_reference_paths degrades gracefully (empty values_by_path) on a WRONGTYPE JSON.GET or a cjson.decode failure, instead of aborting the script"
      contains: "redis.pcall"
    - path: "tests/models/cascade_types.py"
      provides: "CascadeDictCollectionRoot (dict[K,Reference] shape-2 fixture) and CascadeBlanketLeaf.onward (self-referencing blanket edge enabling depth-truncation coverage)"
      contains: "CascadeDictCollectionRoot"
    - path: "tests/integration/pipeline/test_pipeline_noscript_recovery.py"
      provides: "_flush_all_but_cascade(redis_client) helper used by all 3 noscript-recovery tests"
      contains: "_flush_all_but_cascade"
  key_links:
    - from: "tests/integration/pipeline/test_pipeline_noscript_recovery.py::_flush_all_but_cascade"
      to: "rapyer/scripts/registry.py::build_script_texts"
      via: "SCRIPT FLUSH then script_load(build_script_texts()[CASCADE_TTL_APPLY_SCRIPT_NAME]) reloads only the cascade SHA"
      pattern: "build_script_texts"
    - from: "tests/models/cascade_types.py::CascadeDictCollectionRoot"
      to: "rapyer/cascade/planner.py::build_cascade_plan"
      via: "dict[str, Reference[CascadeAuthor]] field is classified as a collection-of-FK edge, mirroring list[Reference[T]]"
      pattern: "CascadeDictCollectionRoot"
    - from: "rapyer/scripts/lua/cascade/apply.lua::read_reference_paths"
      to: "EXPIRE write phase (plan_refresh_keys)"
      via: "the corrupt node's own queue_refresh entry is queued before push_edges runs, so a pcall-guarded read failure never drops that node's own refresh"
      pattern: "redis.pcall"
---

<objective>
Close 4 PR #283 review-round-4 / cascade edge-case gaps: (1) make the noscript-recovery tests flush only data-op scripts (never the cascade TTL script) via a new `build_script_texts` extraction, (2) add missing test coverage for `dict[K, Reference]` cascade (already supported by the planner + Lua, but untested), (3) prove nested-submodel depth-budget truncation actually stops traversal beyond the budget (not just that zero-hop doesn't over-consume it), and (4) make `apply.lua` degrade gracefully instead of aborting when a cascade-reached target key is corrupt/WRONGTYPE.

Purpose: Round out the TTL-cascade feature's edge-case test coverage and remove one real robustness gap (an adversarial/corrupt reached target currently aborts the whole cascade EVALSHA) before this milestone's cross-AI review closes out.
Output: `build_script_texts` helper in `rapyer/scripts/registry.py`; a hardened `read_reference_paths` in `rapyer/scripts/lua/cascade/apply.lua`; `CascadeDictCollectionRoot` + extended `CascadeBlanketLeaf` fixtures in `tests/models/cascade_types.py`; new/updated tests across noscript-recovery, plan-table, apply-lua-unit, and cascade-ttl-apply-integration suites.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md

<interfaces>
**`rapyer/scripts/registry.py` (current shape -- Task 1 extracts from this):**
```python
SCRIPT_REGISTRY: list[tuple[str, str, str]] = [...]  # includes ("cascade", "apply", CASCADE_TTL_APPLY_SCRIPT_NAME)
def _build_scripts(variant: str) -> dict[str, str]: ...
def _inject_sf_dispatch(template: str, sf_base) -> str: ...
def _inject_cascade_plan(template: str, plan: dict[str, "CascadePlanEntry"]) -> str: ...

async def register_scripts(redis_client, is_fakeredis: bool = False) -> None:
    from rapyer.base import REDIS_MODELS
    from rapyer.cascade.planner import build_cascade_plan
    from rapyer.types.special import SpecialFieldType

    variant = FAKEREDIS_VARIANT if is_fakeredis else REDIS_VARIANT
    scripts = _build_scripts(variant)
    cascade_plan = build_cascade_plan(REDIS_MODELS)
    for name, script_text in scripts.items():
        scripts[name] = _inject_sf_dispatch(script_text, SpecialFieldType)
    for name, script_text in scripts.items():
        scripts[name] = _inject_cascade_plan(script_text, cascade_plan)
    for name, script_text in scripts.items():
        sha = await redis_client.script_load(script_text)
        _REGISTERED_SCRIPT_SHAS[name] = sha
```
Extract everything up to (not including) the final `script_load`/SHA-storage loop into `build_script_texts(is_fakeredis: bool = False) -> dict[str, str]`, returning `scripts`. `register_scripts` becomes: `scripts = build_script_texts(is_fakeredis=is_fakeredis)` then the unchanged `script_load` loop.

**`rapyer/scripts/constants.py`:** `CASCADE_TTL_APPLY_SCRIPT_NAME = "cascade_ttl_apply"`.

**`tests/integration/pipeline/test_pipeline_noscript_recovery.py` (current, all 3 tests use `await real_redis_client.execute_command("SCRIPT", "FLUSH")` directly after a stale rationale comment about flush ordering -- both the raw flush calls and the 2 rationale comments are replaced by Task 1).

**`rapyer/scripts/lua/cascade/apply.lua::read_reference_paths` (current, ~L88-111, the Task 4 target):**
```lua
local function read_reference_paths(key, paths)
    local raw = redis.call('JSON.GET', key, unpack(paths))
    local values_by_path = {}
    if not raw or raw == '' then
        return values_by_path
    end
    local decoded = cjson.decode(raw)
    if #paths == 1 then
        local match = decoded[1]
        if match ~= nil and match ~= cjson.null then
            values_by_path[paths[1]] = match
        end
        return values_by_path
    end
    for _, path in ipairs(paths) do
        local matches = decoded[path]
        local match = matches and matches[1]
        if match ~= nil and match ~= cjson.null then
            values_by_path[path] = match
        end
    end
    return values_by_path
end
```
The caller (`plan_refresh_keys`'s while-loop) already calls `queue_refresh(key, item.class)` for a node BEFORE calling `push_edges(key, ...)` (which calls `read_reference_paths`) -- so a node's own refresh is queued regardless of what happens when reading ITS OWN outgoing edges. `redis.pcall` (unlike `redis.call`) returns a Lua table with an `err` field instead of raising on a Redis-level error (e.g. WRONGTYPE); a raw `pcall(cjson.decode, raw)` catches a malformed-JSON decode failure the same way.

**`tests/models/cascade_types.py` (relevant existing fixtures):**
```python
class CascadeBookCollection(AtomicRedisModel):
    """Shape 2: collection-of-FK field carrying the marker on the collection itself."""
    title: str = "untitled"
    co_authors: Annotated[list[Reference[CascadeAuthor]], CascadeTTL()] = Field(default_factory=list)
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)

class CascadeBlanketLeaf(AtomicRedisModel):
    """Plain leaf reached purely via a blanket-enabled global default."""
    name: str = "leaf"
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)

class CascadeBlanketNestedProfile(AtomicRedisModel):
    mentor: Reference[CascadeBlanketLeaf]
    Meta: ClassVar[RedisConfig] = RedisConfig(cascade_ttl=CascadeTTL(depth=2), ttl=CASCADE_FIXTURE_TTL_SECONDS)

class CascadeBlanketNestedHolder(AtomicRedisModel):
    profile: CascadeBlanketNestedProfile
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)

class CascadeNestedDepthRoot(AtomicRedisModel):
    holder: Annotated[Reference[CascadeBlanketNestedHolder], CascadeTTL(depth=1)]
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)

class CascadeChainNode(AtomicRedisModel):
    """next carries no per-field marker -- driven by this class's own blanket Meta.cascade_ttl."""
    name: str = "node"
    next: Optional[Reference["CascadeChainNode"]] = None
    Meta: ClassVar[RedisConfig] = RedisConfig(cascade_ttl=CascadeTTL(), ttl=CASCADE_FIXTURE_TTL_SECONDS)

class CascadeChainRoot(AtomicRedisModel):
    head: Annotated[Reference[CascadeChainNode], CascadeTTL(depth=2)]
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)
```
Existing budget mechanics (verified from apply.lua's `next_hop`): the depth-budget check (`remaining_budget <= 0 -> follow=false`) happens BEFORE the edge's own `depth` value is even read for a non-override (blanket) edge -- so any blanket edge declared on a node that is reached with a budget of exactly 0 is never followed, regardless of that edge's own configured depth. This is the mechanism Task 3's new test exercises: `CascadeNestedDepthRoot(depth=1)` enters `holder` at budget=1; the zero-hop `.profile` field consumes none of it; the real hop into `.mentor` (via `CascadeBlanketNestedProfile.Meta.cascade_ttl(depth=2)`, a blanket, non-override edge) decrements 1->0; `mentor` is therefore reached with budget=0, so anything `mentor` itself would reach only through its OWN blanket edge is never followed.

**Existing `_apply_cascade` test helpers** (identical shape in both `tests/unit/cascade/test_cascade_apply_lua.py` and `tests/integration/foreign_keys/test_cascade_ttl_apply.py`):
```python
async def _apply_cascade(fake_redis_client, root, cascade=True):
    return await arun_sha(
        fake_redis_client, type(root).Meta, CASCADE_TTL_APPLY_SCRIPT_NAME, 1,
        root.key, type(root).__name__, SPECIAL_FIELD_KEY_PREFIX, type(root).Meta.ttl,
        1 if cascade else 0,
    )
```
(the integration version omits the trailing `cascade` ARGV entirely -- keep that asymmetry as-is, do not add a `cascade` kwarg to the integration helper.)

**`tests/unit/cascade/conftest.py` / `tests/integration/foreign_keys/conftest.py`:** each maintains its own `CASCADE_PLANNER_MODELS` / `CASCADE_INTEGRATION_MODELS` list (imports + a flat list of classes) that the `setup_fake_redis_for_cascade_apply` / `setup_real_redis_for_cascade_apply` fixtures wire `Meta.redis` for and pass to `resolve_relational_targets`. `CascadeBookCollection` is present in both lists today -- add `CascadeDictCollectionRoot` alongside it in both.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Flush-all-but-cascade in noscript-recovery tests</name>
  <files>rapyer/scripts/registry.py, tests/integration/pipeline/test_pipeline_noscript_recovery.py</files>
  <action>
In `rapyer/scripts/registry.py`, extract a new pure function `build_script_texts(is_fakeredis: bool = False) -> dict[str, str]` that does exactly what `register_scripts` currently does UP TO (not including) the final `script_load`/SHA-storage loop: resolve the variant, call `_build_scripts(variant)`, build the cascade plan via `build_cascade_plan(REDIS_MODELS)`, run the `_inject_sf_dispatch` loop, run the `_inject_cascade_plan` loop, and return the resulting `scripts` dict. Move the existing "Late imports" explanatory comment onto `build_script_texts` (it now belongs there). Rewrite `register_scripts` to call `scripts = build_script_texts(is_fakeredis=is_fakeredis)` and keep only the unchanged `script_load` + `_REGISTERED_SCRIPT_SHAS` loop after it. This is a behavior-preserving refactor -- `register_scripts`'s observable behavior (which SHAs get registered, with what injected text) must be byte-identical to before.

In `tests/integration/pipeline/test_pipeline_noscript_recovery.py`, add imports `from rapyer.scripts.constants import CASCADE_TTL_APPLY_SCRIPT_NAME` and `from rapyer.scripts.registry import build_script_texts`. Add a module-level helper:
```python
async def _flush_all_but_cascade(redis_client):
```
Body: `await redis_client.execute_command("SCRIPT", "FLUSH")` then `await redis_client.script_load(build_script_texts()[CASCADE_TTL_APPLY_SCRIPT_NAME])`. Give it a short WHY comment: Redis has no selective SCRIPT FLUSH, so flush everything then reload only the cascade TTL script's SHA -- this leaves every data-op script (list/dict/numeric/atomic) missing (exercising `_apipeline`'s NOSCRIPT self-heal) while TTL-refresh (which routes through the cascade script) keeps working uninterrupted.

Replace all 3 occurrences of `await real_redis_client.execute_command("SCRIPT", "FLUSH")` with `await _flush_all_but_cascade(real_redis_client)`. Delete the two "Flush AFTER the establishing save... does not self-heal NOSCRIPT (see NOSCRIPT-ISSUE.md)" rationale comments in the first two tests (now stale: the cascade script is never missing, so flush-vs-save ordering no longer matters) -- do not replace them with new prose, the helper's own comment already covers the WHY. Leave the "Arrange" comment on the third (`disable_noscript_recovery`) test as-is except for swapping in the new helper call.

Do not change any assertions, fixture usage, or the `disable_noscript_recovery` test's expected `PersistentNoScriptError` behavior.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && REDIS_DB=0 python -m pytest tests/integration/pipeline/test_pipeline_noscript_recovery.py -q -p no:randomly && REDIS_DB=0 python -m pytest tests -q -p no:randomly && black --check --diff rapyer/scripts/registry.py tests/integration/pipeline/test_pipeline_noscript_recovery.py && ruff check rapyer/scripts/registry.py tests/integration/pipeline/test_pipeline_noscript_recovery.py</automated>
  </verify>
  <done>build_script_texts exists and register_scripts delegates to it with unchanged observable behavior; all 3 noscript-recovery tests pass using _flush_all_but_cascade (2 prove _apipeline self-heals data-op scripts while cascade stays loaded, 1 still raises PersistentNoScriptError); full suite green; black/ruff clean on both files. Commit as `test(cascade): flush all-but-cascade script in noscript-recovery tests (PR #283 review)`.</done>
</task>

<task type="auto">
  <name>Task 2: Cover dict[K, Reference] FK-collection cascade</name>
  <files>tests/models/cascade_types.py, tests/unit/cascade/conftest.py, tests/integration/foreign_keys/conftest.py, tests/unit/cascade/test_cascade_plan_table.py, tests/integration/foreign_keys/test_cascade_ttl_apply.py</files>
  <action>
In `tests/models/cascade_types.py`, add a new model directly after `CascadeBookCollection`, mirroring its shape but for the dict-collection variant:
```python
class CascadeDictCollectionRoot(AtomicRedisModel):
    """Shape 2 variant: dict[K, Reference] carries the marker on the collection itself."""

    title: str = "untitled"
    co_authors: Annotated[dict[str, Reference[CascadeAuthor]], CascadeTTL()] = Field(
        default_factory=dict
    )

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=CASCADE_FIXTURE_TTL_SECONDS)
```

Register it: in `tests/unit/cascade/conftest.py`, import `CascadeDictCollectionRoot` and add it to `CASCADE_PLANNER_MODELS` next to `CascadeBookCollection`. In `tests/integration/foreign_keys/conftest.py`, import `CascadeDictCollectionRoot` and add it to `CASCADE_INTEGRATION_MODELS` next to `CascadeBookCollection`.

In `tests/unit/cascade/test_cascade_plan_table.py`, add `test_shape2_dict_of_fk_produces_exactly_one_edge_marked_collection` directly after `test_shape2_collection_of_fk_produces_exactly_one_edge_marked_collection`, following its exact structure: `plan = build_cascade_plan([CascadeDictCollectionRoot, CascadeAuthor])`; assert `len(plan["CascadeDictCollectionRoot"].fks) == 1`, `edges[0].is_collection is True`, `edges[0].target == "CascadeAuthor"`, `edges[0].path == "$.co_authors"`. Add AAA markers (`# Act` / `# Assert`, no distinct Arrange step, matching the sibling test's style). Import `CascadeDictCollectionRoot` at the top of the file.

In `tests/integration/foreign_keys/test_cascade_ttl_apply.py`, add `test_cascade_apply_refreshes_every_dict_value_fk_element_sanity` directly after `test_cascade_apply_refreshes_every_collection_of_fk_element_sanity`, following its exact structure but constructing `CascadeDictCollectionRoot(title="anthology", co_authors={"a": author_a.key, "b": author_b.key})` instead of the list form. Persist `author_a.key`, `author_b.key`, and the root's key; call `_apply_cascade(real_redis_client, book)`; assert all 3 keys have `ttl(...) > 0`. Add a short comment noting this is the dict-value counterpart proving JSON.GET's `pairs()`-based element iteration in `push_edges` works identically for a JSON-object-shaped match as for a JSON-array one. Import `CascadeDictCollectionRoot` at the top of the file. Use AAA markers.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && REDIS_DB=0 python -m pytest tests/unit/cascade/test_cascade_plan_table.py tests/integration/foreign_keys/test_cascade_ttl_apply.py -q -p no:randomly && REDIS_DB=0 python -m pytest tests -q -p no:randomly && black --check --diff tests/models/cascade_types.py tests/unit/cascade/conftest.py tests/integration/foreign_keys/conftest.py tests/unit/cascade/test_cascade_plan_table.py tests/integration/foreign_keys/test_cascade_ttl_apply.py && ruff check tests/models/cascade_types.py tests/unit/cascade/conftest.py tests/integration/foreign_keys/conftest.py tests/unit/cascade/test_cascade_plan_table.py tests/integration/foreign_keys/test_cascade_ttl_apply.py</automated>
  </verify>
  <done>CascadeDictCollectionRoot exists and is registered in both model lists; the plan-table test proves exactly one collection-marked edge; the real-Redis integration test proves every dict-value FK element gets refreshed; full suite green; black/ruff clean on all 5 touched files. Commit as `test(cascade): cover dict[K, Reference] FK-collection cascade (PR #283 review)`.</done>
</task>

<task type="auto">
  <name>Task 3: Prove nested-submodel depth-budget truncation</name>
  <files>tests/models/cascade_types.py, tests/unit/cascade/test_cascade_apply_lua.py</files>
  <action>
In `tests/models/cascade_types.py`, extend `CascadeBlanketLeaf` with a self-referencing onward FK driven by its own blanket default, so it can be chained one hop further:
```python
class CascadeBlanketLeaf(AtomicRedisModel):
    """Plain leaf reached purely via a blanket-enabled global default; also
    carries an onward blanket edge so a node reached at budget=0 (via
    another class's blanket decrement) proves depth-budget truncation."""

    name: str = "leaf"
    onward: Optional[Reference["CascadeBlanketLeaf"]] = None

    Meta: ClassVar[RedisConfig] = RedisConfig(
        cascade_ttl=CascadeTTL(), ttl=CASCADE_FIXTURE_TTL_SECONDS
    )
```
`Optional` and `CascadeTTL` are already imported in this module. This is additive and inert for every existing use of `CascadeBlanketLeaf` (`CascadeBlanketRoot`, `CascadeBlanketCollectionRoot`, `CascadeBlanketOptOut`, `CascadeBlanketNestedProfile.mentor`): none of those ever set `onward`, so the field stays `null` and no new edge is ever taken by any pre-existing test. Adding `Meta.cascade_ttl` here only governs edges DECLARED ON `CascadeBlanketLeaf` itself (i.e. the new `onward` field) -- it has no effect on how OTHER classes classify their OWN fields that target `CascadeBlanketLeaf`.

In `tests/unit/cascade/test_cascade_apply_lua.py`, add a new test directly after `test_nested_submodel_zero_hop_does_not_consume_depth_budget`, reusing that test's exact chain (`CascadeNestedDepthRoot(depth=1) -> CascadeBlanketNestedHolder -> CascadeBlanketNestedProfile -> CascadeBlanketLeaf` via `mentor`) and extending it one hop further via the new `onward` field:
```python
@pytest.mark.asyncio
async def test_node_beyond_nested_depth_budget_is_never_reached_sanity(
    fake_redis_client,
):
```
Arrange: `beyond = await CascadeBlanketLeaf(name="beyond").asave()`; `mentor = await CascadeBlanketLeaf(name="mentor", onward=beyond.key).asave()`; `holder = await CascadeBlanketNestedHolder(profile=CascadeBlanketNestedProfile(mentor=mentor.key)).asave()`; `root = await CascadeNestedDepthRoot(holder=holder.key).asave()`; persist all 4 keys (`root.key`, `holder.key`, `mentor.key`, `beyond.key`). Act: `await _apply_cascade(fake_redis_client, root)`. Assert: every one of `(root.key, holder.key, mentor.key)` has `ttl(...) > 0` (in-budget nodes still refresh, same contract as the sibling zero-hop test) AND `await fake_redis_client.ttl(beyond.key) in (-1, -2)` (the node reachable only past mentor's own exhausted budget=0 is never queued for refresh). Add a comment explaining the budget arithmetic: root's depth=1 override enters holder at budget=1; the zero-hop `.profile` field doesn't consume it; the real hop into `.mentor` (via `CascadeBlanketNestedProfile`'s own blanket depth=2) decrements 1->0; mentor's own blanket `onward` edge is therefore evaluated at budget=0 and never followed. Use AAA markers.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && REDIS_DB=0 python -m pytest tests/unit/cascade/test_cascade_apply_lua.py -q -p no:randomly && REDIS_DB=0 python -m pytest tests -q -p no:randomly && black --check --diff tests/models/cascade_types.py tests/unit/cascade/test_cascade_apply_lua.py && ruff check tests/models/cascade_types.py tests/unit/cascade/test_cascade_apply_lua.py</automated>
  </verify>
  <done>CascadeBlanketLeaf.onward exists and is inert for every pre-existing test; the new test proves root/holder/mentor refresh while beyond stays at TTL -1/-2; every pre-existing dangling/graph/depth test in this file still passes; black/ruff clean. Commit as `test(cascade): prove nested-submodel depth-budget truncation (PR #283 review)`.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Skip a corrupt/WRONGTYPE reached target instead of aborting</name>
  <files>rapyer/scripts/lua/cascade/apply.lua, tests/integration/foreign_keys/test_cascade_ttl_apply.py, .planning/codebase/CONCERNS.md</files>
  <behavior>
    - On real Redis Stack: a `JSON.GET` against a WRONGTYPE key (e.g. a plain Redis string, not a RedisJSON document) inside `read_reference_paths` raises today (aborting the whole cascade EVALSHA) and must NOT raise after the fix -- it returns an empty `values_by_path`, so the caller's `push_edges` finds no edges to follow out of that node. This RED-before/GREEN-after contract is proven ONLY by a `real_redis_client` integration test: fakeredis 2.34.1's `JSON.GET` does not emulate WRONGTYPE (it returns `"[]"` regardless of the guard), so a fakeredis test would pass identically before and after the fix and cannot serve as the regression guard.
    - A `cjson.decode` failure on malformed `raw` output is likewise swallowed into an empty `values_by_path`, not raised.
    - The corrupt node's own key is still `EXPIRE`d in the write phase (its `queue_refresh` entry was already queued by the caller before `push_edges`/`read_reference_paths` ever runs) -- it is never counted as dangling, and no traversal continues past it.
    - `CascadeResult`/dangling-count return shape is unchanged; no new counter is added.
  </behavior>
  <action>
In `rapyer/scripts/lua/cascade/apply.lua`'s `read_reference_paths` function (~L88-111), change `local raw = redis.call('JSON.GET', key, unpack(paths))` to `local raw = redis.pcall('JSON.GET', key, unpack(paths))`, then immediately check `if type(raw) == 'table' and raw.err then return values_by_path end` before the existing `if not raw or raw == ''` check -- `redis.pcall` (unlike `redis.call`) returns an error table instead of raising on a Redis-level error such as WRONGTYPE. Add a short comment above this check explaining why: a WRONGTYPE/corrupt reached target becomes a dead end for further traversal, not an aborted cascade -- its own key was already queued for refresh by the caller. Then wrap the existing `local decoded = cjson.decode(raw)` as `local ok, decoded = pcall(cjson.decode, raw)` followed by `if not ok then return values_by_path end`, covering a malformed-JSON decode failure the same way. Do not touch anything else in the file -- `push_edges`, `queue_refresh`, `plan_refresh_keys`, and the final `{dangling_children_count, dangling_special_count}` return shape are all unchanged.

In `tests/integration/foreign_keys/test_cascade_ttl_apply.py`, import `CascadeChainNode, CascadeChainRoot` alongside the existing imports, and add `test_cascade_apply_skips_corrupt_wrongtype_reached_target_sanity` against `real_redis_client` -- this is the SOLE regression guard for this fix (see the CONCERNS.md entry added below for why a fakeredis equivalent would not test anything). Arrange: `await real_redis_client.set("CascadeChainNode:corrupt", "garbage")` (a plain string at a key shaped like a CascadeChainNode key, so `JSON.GET` on it raises a genuine WRONGTYPE error on real Redis Stack); `root = await CascadeChainRoot(head="CascadeChainNode:corrupt").asave()`; persist `root.key` and `"CascadeChainNode:corrupt"`. Act: `await _apply_cascade(real_redis_client, root)` -- before the Lua fix this call raises (RED), after the fix it must not raise (GREEN). Assert: `await real_redis_client.ttl(root.key) > 0` and `await real_redis_client.ttl("CascadeChainNode:corrupt") > 0` (the corrupt key itself still gets refreshed; no traversal continues past it). Use AAA markers.

Append a short new entry to `.planning/codebase/CONCERNS.md` under "Known Bugs (history of fragility, from CHANGELOG)", matching the existing "fakeredis vs real Redis behavioral divergence" bullet's format (Symptoms/Files/Trigger/Workaround). Title it "fakeredis's JSON.GET does not emulate WRONGTYPE". Symptoms: fakeredis 2.34.1 returns `"[]"` from `JSON.GET` against a plain-string (non-JSON) key instead of raising a WRONGTYPE error the way real Redis Stack does. Files: `rapyer/scripts/lua/cascade/apply.lua::read_reference_paths` (the `redis.pcall('JSON.GET', ...)` WRONGTYPE guard added by this task). Trigger: writing a fakeredis-only regression test for any code path that guards against a `JSON.GET` WRONGTYPE error -- the guard is untestable under fakeredis. Workaround: regression coverage for `JSON.GET` WRONGTYPE handling must live in `tests/integration/foreign_keys/` against `real_redis_client`, never `tests/unit/cascade/` against `fake_redis_client` alone.
  </action>
  <verify>
    <automated>cd /Users/yedidyakfir/Documents/rapyer && REDIS_DB=0 python -m pytest tests/integration/foreign_keys/test_cascade_ttl_apply.py -q -p no:randomly && REDIS_DB=0 python -m pytest tests -q -p no:randomly && black --check --diff tests/integration/foreign_keys/test_cascade_ttl_apply.py && ruff check tests/integration/foreign_keys/test_cascade_ttl_apply.py</automated>
  </verify>
  <done>apply.lua's read_reference_paths degrades gracefully (empty values_by_path, no raise) on a WRONGTYPE JSON.GET or a decode failure, proven by a real-Redis integration test that is RED before the fix (script raises) and GREEN after (no raise, root TTL>0, corrupt key TTL>0, no traversal beyond it); no fakeredis test is used as a regression guard for this fix; CONCERNS.md records the fakeredis JSON.GET WRONGTYPE-emulation gap so no one relies on the fakeredis suite to catch a regression here; every pre-existing dangling/graph/depth Lua test still passes; black/ruff clean. Commit as `fix(cascade): skip a corrupt/WRONGTYPE reached target instead of aborting the cascade (PR #283 review)`.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| FK-graph traversal -> reached target key | A cascade root's FK graph may lead to a key that is corrupt, WRONGTYPE, or otherwise not the expected RedisJSON document -- this data is read and `cjson.decode`d server-side inside `apply.lua`. |
| Test harness <-> real Redis (SCRIPT FLUSH) | Test-only script-cache manipulation (Task 1); not a production code path. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-ukx-01 | Denial of Service | `apply.lua::read_reference_paths` | mitigate | Wrap `JSON.GET` in `redis.pcall` and `cjson.decode` in `pcall` (Task 4) so one corrupt/WRONGTYPE reached target degrades to a dead end instead of aborting the entire EVALSHA for every key sharing that cascade root. |
| T-quick-ukx-02 | Tampering (behavior drift from the registry.py extraction) | `rapyer/scripts/registry.py::build_script_texts` | accept | Extraction is purely mechanical (same SF-dispatch + cascade-plan injection order, same output); full suite re-run after Task 1 is the regression backstop, not just diff inspection. |
| T-quick-ukx-03 | Information Disclosure / Denial of Service (unbounded traversal cost) | `apply.lua` depth-budget enforcement | accept | Already mitigated by the existing max-depth/visited-budget machinery shipped in PR #283; Task 3 only adds test coverage proving the existing enforcement actually truncates, it does not change enforcement logic. |

No npm/pip/cargo package installs are introduced by this plan -- the package-legitimacy gate does not apply.
</threat_model>

<verification>
1. `REDIS_DB=0 python -m pytest tests -q -p no:randomly` passes with 0 failures after each of the 4 tasks (real Redis Stack on localhost:6370).
2. `black --check --diff` and `ruff check` clean on every touched file after each task.
3. `git diff` on `rapyer/scripts/registry.py` shows a pure extraction (no change to `SCRIPT_REGISTRY`, `_inject_sf_dispatch`, `_inject_cascade_plan`, or the final SHA-storage loop's semantics).
4. `git diff` on `rapyer/scripts/lua/cascade/apply.lua` touches only `read_reference_paths` (the two `pcall`/`redis.pcall` guards) -- `push_edges`, `queue_refresh`, `plan_refresh_keys`, and the final return shape are untouched.
</verification>

<success_criteria>
- Noscript-recovery tests exercise `_apipeline`'s real NOSCRIPT self-heal path without ever making the cascade TTL script itself missing.
- `dict[K, Reference]` cascade has explicit plan-table and real-Redis-apply coverage, matching the existing `list[Reference[T]]` coverage.
- Nested-submodel (shape 3) depth-budget truncation is proven, not just zero-hop non-consumption.
- `apply.lua` never aborts on a corrupt/WRONGTYPE reached target; the target's own key still refreshes and traversal stops there.
- Full suite green and black/ruff clean after every task; 4 atomic commits, one per task, using the exact messages given in each task's `<done>`.
</success_criteria>

<output>
Create `.planning/quick/260715-ukx-pr283-review-round4-and-cascade-edge-cas/260715-ukx-SUMMARY.md` when done
</output>
