---
phase: 01-classify-sf-held-fk-references-into-the-cascade-plan
reviewed: 2026-07-24T16:26:09Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - rapyer/cascade/planner.py
  - tests/models/cascade_types.py
  - tests/unit/cascade/conftest.py
  - tests/unit/cascade/test_cascade_sf_held_ref_plan.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-07-24T16:26:09Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the SF-held-ref classification pass added to `build_cascade_plan`: the
new `sf_container` discriminator on the frozen `CascadeEdge` dataclass and the
`_static_walk_sf_fk_edges` discovery pass, plus the supporting fixtures and unit
tests.

The core logic is correct. I traced the classification path end-to-end and
verified the following against the actual code:

- **set/zset discrimination is safe.** `RedisPriorityQueue` is NOT a subclass of
  `RedisSet` (both independently subclass `SpecialFieldType`; `RedisSet(set,
  SpecialFieldType)`, `RedisPriorityQueue(SpecialFieldType)`), so the
  `if safe_issubclass(origin, RedisSet)` / `elif ... RedisPriorityQueue` ordering
  cannot mis-tag a priority queue as `"set"`.
- **Target resolution reuse is sound.** `_unwrap_relational_target` recurses
  `RedisSet[Reference[T]] → ForeignKey[T] → T` (confirmed `Reference` aliases
  `ForeignKey`, a `RelationalFieldType`; `resolve_generic_args` returns the args).
  Non-ref SF fields (`RedisSet[str]`, `RedisPriorityQueue[float]` on
  `CascadeSpecialChild`) correctly resolve to `None` and emit no edge.
- **No double emission.** SF fields land only in `_special_field_names`, never in
  `_relational_field_names`/`_contain_fk`, so `_static_walk_fk_edges` and
  `_static_walk_sf_fk_edges` do not both fire for the same field (test
  `test_guard_redis_set_contains_fk_field_is_false...` guards this).
- **Precedence + fail-fast are correct.** Field-spec-over-blanket precedence,
  opt-out, blanket depth, `resets_depth_budget=edge.override`, and the target /
  root TTL-missing validation paths all behave as the tests assert.
- **Serialization stays additive.** `sf_container` defaults to `None` and is
  dropped by `_drop_none_values`, keeping non-SF plan bytes/hash stable
  (test `test_non_sf_edge_json_has_no_sf_container_key`).

One warning: the discovery pass does not recurse into nested inline sub-models,
diverging from its two sibling walkers. Details below.

## Warnings

### WR-01: SF-held-ref discovery does not recurse into nested inline sub-models (asymmetry with the suffix/FK walkers)

**File:** `rapyer/cascade/planner.py:198-237` (`_static_walk_sf_fk_edges`), contrasted with `rapyer/cascade/planner.py:240-267` (`_static_walk_special_suffixes`) and `166-174` (`_static_walk_fk_edges` nested recursion)

**Issue:** `_static_walk_sf_fk_edges` iterates only `model_cls._special_field_names`
(the model's OWN special fields) and never descends into nested inline
sub-models. Its two sibling passes both do descend:

- `_static_walk_fk_edges` recurses into nested sub-models via
  `_unwrap_nested_model_cls`, emitting inline FK edges with compound paths
  (`$.profile.mentor`).
- `_static_walk_special_suffixes` recurses via `_contain_sf`, emitting dotted
  suffixes for nested SF fields (`profile.refs`).

The concrete consequence: if a nested inline sub-model holds a
`RedisSet[Reference[T]]` / `RedisPriorityQueue[Reference[T]]` field, the parent's
plan entry WILL get a refresh-only suffix (`profile.refs`, so the SF container key
is `EXPIRE`d) but WILL NOT get an SF-held-ref edge (its members' FK targets are
never followed). That is exactly the reach gap this phase set out to close — left
open, silently, for the nested case. Registering the nested class standalone does
not compensate: its SF key at runtime lives under the parent key with the
`profile.refs` suffix, not under a standalone `{NestedClass}` key, so a
standalone entry's `path="refs"` edge points at the wrong key.

This is not exercised by any current fixture (no fixture nests an SF-ref field),
and the CONTEXT defers "SF containers holding nested inline submodels." Note the
deferred item is the inverse shape (a container holding a submodel); the gap here
is a nested submodel holding a container, which the deferral does not clearly
cover. Flagging so the intent is made explicit rather than left as a latent,
undocumented divergence between three passes that a maintainer would reasonably
expect to behave alike.

**Fix:** If nested SF-ref reach is intended for a later phase, add an explicit
limitation note to the `_static_walk_sf_fk_edges` docstring (it currently claims
to append an edge "for each SF-held-ref field ... directly on model_cls" without
stating the nested exclusion) so the divergence from the recursing siblings is
documented. If nested reach is intended now, mirror the sub-model recursion
already present in the other two walkers, e.g.:

```python
def _static_walk_sf_fk_edges(model_cls, fks, parent_path=""):
    ...
    for field_name in model_cls._special_field_names:
        annotation = model_cls.model_fields[field_name].annotation
        target_cls = _unwrap_relational_target(annotation)
        ...
        path = f"{parent_path}.{field_name}".lstrip(".")
        fks.append(CascadeEdge(path=path, ...))
    # descend into nested inline sub-models that themselves hold SF-ref fields
    for field_name in model_cls._contain_sf:
        nested_cls = _unwrap_nested_model_cls(model_cls.model_fields[field_name].annotation)
        if nested_cls is not None:
            _static_walk_sf_fk_edges(nested_cls, fks, f"{parent_path}.{field_name}")
```

## Info

### IN-01: `"set"` / `"zset"` discriminator literals are an untyped inline contract with Phase-2 Lua

**File:** `rapyer/cascade/planner.py:217,219`

**Issue:** The `sf_container` values `"set"` and `"zset"` are raw string literals
produced here and consumed by the Phase-2 Lua (`SMEMBERS` vs `ZRANGE` branch, per
the dataclass docstring). They are the cross-module wire contract but are not
named constants, so a typo or drift on either side fails silently rather than at
import time. The dataclass docstring documents the intended values, which
mitigates this.

**Fix:** Consider hoisting to module-level constants (e.g.
`SF_CONTAINER_SET = "set"`, `SF_CONTAINER_ZSET = "zset"`) reused by the Lua
codegen/constants once Phase 2 lands, so both ends reference one source of truth.

### IN-02: `_unwrap_relational_target` is computed before the container-kind guard

**File:** `rapyer/cascade/planner.py:210-221`

**Issue:** For every entry in `_special_field_names`, `_unwrap_relational_target`
(a recursive annotation walk) runs before the `RedisSet`/`RedisPriorityQueue`
container check. A non-set/zset special field that happened to wrap a relational
target would do the full unwrap and then hit `else: continue`. This is harmless
today (only set/zset are special ref containers in scope) and out of the v1
performance scope; noting only as a minor ordering nit for readability — checking
the container kind first would make the "only set/zset are eligible" precondition
read more clearly.

**Fix:** Optional — reorder so the `origin`/`sf_container` container check gates
the `_unwrap_relational_target` call. No behavioral change.

---

_Reviewed: 2026-07-24T16:26:09Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
