---
phase: 02-traverse-sf-held-references-server-side-and-re-arm-children
reviewed: 2026-07-25T22:39:35Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - rapyer/base.py
  - rapyer/cascade/planner.py
  - rapyer/scripts/lua/cascade/library.lua
  - rapyer/types/priority_queue.py
  - rapyer/types/redis_set.py
  - tests/models/cascade_types.py
  - tests/integration/foreign_keys/test_cascade_sf_held_ref_apply.py
  - tests/integration/foreign_keys/test_cascade_sf_held_ref_public_api.py
  - tests/unit/cascade/test_cascade_sf_held_ref_fakeredis_fallback.py
  - tests/unit/cascade/test_cascade_sf_only_trigger_gate.py
  - docs/documentation/special-fields/ttl-cascade.md
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-07-25T22:39:35Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the SF-held-ref server-side traversal work: the new Lua `push_sf_edge`
branch (`library.lua`), the `_dump_members` validate-before-dump change in
`redis_set.py`/`priority_queue.py`, the planner's SF-edge classifier +
forward-ref resolver (`planner.py`), and the model-level trigger gate
(`base.py`). No blockers found — the core correctness properties hold up under
adversarial tracing and I verified the load-bearing ones empirically:

- **Member encoding matches the Lua decoder.** Confirmed both `RedisSet` and
  `RedisPriorityQueue` store FK members as JSON-encoded key strings
  (`"CascadeAuthor:<uuid>"`), which `cjson.decode` in `push_sf_edge` turns back
  into a plain key string. Adding via a raw key string vs a `ForeignKey`
  normalizes to the *same* member (deduped to one), which is exactly the
  validate-before-dump fix working as intended.
- **SF key construction is correct.** The Lua builds
  `special_prefix .. ':' .. parent_key .. ':' .. edge.path`, and `edge.path`
  for an SF edge is the bare field name; this matches
  `SpecialFieldType.special_field_key` (`__rapyer_special__:{model_key}:{name}`)
  for the direct-field-only scope the planner emits.
- **Cycle/diamond safety holds.** Traced the self-ref (`visited[root]=UNBOUNDED`
  rejects the cycle push) and the SET+ZSET dual-edge diamond (second push loses
  the `budget_is_larger` check) — both terminate and re-arm exactly once.
- **Trigger gate + forward-ref resolution verified.** Built the plan for all
  cascade fixtures: SF edges carry the right `sf_container`, the self-ref
  `ForwardRef` resolves via the registry, the opt-out model yields zero edges,
  and `_contains_foreign_key()` flips to `True` only for cascade-enabled SF-only
  parents.
- Malformed-member tolerance, fakeredis fallback, and the trigger gate are all
  covered by passing tests (the 5 unit tests run green here).

The two warnings are narrow observability/robustness gaps, not incorrect
behavior on the happy path.

## Warnings

### WR-01: Unresolvable SF-held forward-ref silently disables cascade with no startup error

**File:** `rapyer/cascade/planner.py:44-47` (and `_static_walk_sf_fk_edges:242-243`)
**Issue:** `_resolve_forward_ref` returns `None` when no registered model
matches the forward-ref name. `_unwrap_relational_target` then returns `None`,
and `_static_walk_sf_fk_edges` does `continue`, so the SF edge is never emitted.
Because `validate_cascade_ttl_targets` only inspects edges that were actually
emitted, a *dropped* edge is invisible to the startup validation that otherwise
fails fast on missing/ttl-less targets. Net effect: a mistyped or
not-yet-registered self-ref target (e.g. `RedisSet[Reference["CascadeSetRefSelfNod"]]`
with a typo, or a target carrying `init_with_rapyer=False`) silently produces
**no cascade edge and no error** — `class_declares_cascade_enabled_sf_ref_edge`
returns `False`, the trigger gate stays off, and members are never re-armed. The
inline path shares the same silent-drop pattern, but the registry-name lookup
introduced here is a new failure surface where a plausible misconfiguration
degrades to "cascade silently off."
**Fix:** Make the drop observable. Minimal option — log a warning when a
forward-ref FK target can't be resolved:
```python
def _resolve_forward_ref(forward_ref: ForwardRef) -> Any | None:
    from rapyer.base import REDIS_MODELS

    name = forward_ref.__forward_arg__
    for model in REDIS_MODELS:
        if model.__name__ == name:
            return model
    logger.warning(
        "Cascade: SF-held forward ref %r did not resolve to a registered "
        "model; the cascade edge was dropped (no traversal for this field).",
        name,
    )
    return None
```
Stronger option: have `build_cascade_plan` collect unresolved SF forward refs
and surface them through the existing `validate_cascade_ttl_targets` fail-fast
path so a typo is caught at `init_rapyer()` rather than silently at runtime.

### WR-02: `validate_python` context asymmetry between RedisSet and RedisPriorityQueue `_dump_members`

**File:** `rapyer/types/redis_set.py:32` vs `rapyer/types/priority_queue.py:34-36`
**Issue:** The two SF containers apply *different* validation contexts to their
members in the new validate-before-dump step. `RedisSet` calls
`self._adapter.validate_python(set(values))` with **no** context;
`RedisPriorityQueue` calls
`self._adapter.validate_python(list(values), context={REDIS_DUMP_FLAG_NAME: True})`
**with** the redis context. This asymmetry is *required today* by the two
containers' different `_validate_wrap` guards (RedisSet's wrap does
`json.loads(m)` when the redis flag is set — wrong for raw python members;
RedisPriorityQueue's wrap *raises* on a bare list unless the flag is set), and
it is harmless for FK/scalar inner types (verified: FK validation ignores
context). The risk is future-facing: `RedisSet` validates its members in
*non-redis* mode and then dumps them in *redis* mode. Any inner type whose
validator branches on `REDIS_DUMP_FLAG_NAME` (e.g. a pickled/safe-load member
type) would be validated under the wrong mode and could round-trip incorrectly
inside a set while behaving correctly inside a queue — a subtle, hard-to-spot
divergence.
**Fix:** Document the intentional asymmetry with a short comment on each call
site referencing the opposing `_validate_wrap` guard, or (better) constrain
SF-container inner types to context-insensitive types and add a test asserting
set/queue members round-trip identically for a non-FK complex inner type, so a
future regression is caught rather than latent.

## Info

### IN-01: `is_collection=True` on SF edges is dead data for the SF Lua branch

**File:** `rapyer/cascade/planner.py:260` and `rapyer/scripts/lua/cascade/library.lua:229-252`
**Issue:** `_static_walk_sf_fk_edges` sets `is_collection=True` on every SF edge,
but `push_sf_edge` never reads `edge.is_collection` — it always iterates
`SMEMBERS`/`ZRANGE` members. The field is meaningful only for the inline branch
(`push_edges`, which does check `edge.is_collection`). Harmless, but a reader
tracing the SF path may expect the flag to matter and waste time.
**Fix:** Add a one-line comment on the SF `CascadeEdge` construction noting
`is_collection` is inert for SF edges (members are always iterated), or drop it
from the SF-edge payload if the plan JSON size is worth trimming.

### IN-02: `_cascade_sf_ref_edge_flag` cache is never invalidated

**File:** `rapyer/base.py:248-259`
**Issue:** `_has_cascade_enabled_sf_ref_edge` memoizes its result on the class
via `setattr` and never invalidates it. If the flag were ever computed during a
window where an SF-held forward-ref target is not yet in `REDIS_MODELS` (see
WR-01), it would cache `False` permanently. In the current design the method is
only reached at runtime (`refresh_ttl`/`aset_ttl`), well after `init_rapyer()`
completes registration, so this cannot fire today — but the cache-forever
behavior turns any premature call into a silent, sticky wrong answer.
**Fix:** Either note in the comment that the cache assumes registration is
complete at first call, or clear `_cascade_sf_ref_edge_flag` in the init/plan
build path so a rebuild picks up newly registered targets.

### IN-03: `push_sf_edge` `not edge.recurse_into_target` branch is dead today (as documented)

**File:** `rapyer/scripts/lua/cascade/library.lua:234-236`
**Issue:** Same dead-but-intentional seam the inline branch already documents at
lines 286-294: no edge the planner currently emits sets
`recurse_into_target=False`, so the `budget = 0` branch in `push_sf_edge` is
never exercised. Unlike the inline branch, the SF branch carries no comment
explaining the branch is a forward-looking seam.
**Fix:** Mirror the inline branch's explanatory comment on the SF
`if not edge.recurse_into_target then budget = 0 end` so the two dead seams read
consistently.

---

_Reviewed: 2026-07-25T22:39:35Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
