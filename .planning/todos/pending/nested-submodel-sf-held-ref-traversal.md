---
type: todo
created: 2026-07-24
source: 01-REVIEW.md (WR-01)
resolves_phase: 2
priority: medium
---

# Nested sub-model SF-held-ref traversal

## Context
Phase 1's `_static_walk_sf_fk_edges` (rapyer/cascade/planner.py) classifies
`RedisSet[Reference[T]]` / `RedisPriorityQueue[Reference[T]]` fields declared
**directly** on a model. It intentionally does NOT recurse into nested inline
sub-models, unlike its sibling walkers `_static_walk_fk_edges` and
`_static_walk_special_suffixes`.

## Gap (code review WR-01)
A nested inline sub-model holding an SF-held ref (e.g. `parent.profile.refs`
where `profile` is an inline sub-model with a `RedisSet[Reference[T]]`) gets its
refresh-only special suffix emitted (the container key is EXPIRE'd) but **no
traversal edge** — so the refs inside it are never followed. This silently
re-opens, for the nested case only, the exact reach gap Phase 1 closed for the
direct case. Currently undocumented-in-behavior and untested.

## Action for Phase 2
When implementing server-side traversal, decide and implement one of:
1. Mirror the sub-model recursion the other two walkers already have so nested
   SF-held refs emit a traversal edge (with the correct dotted `path` suffix), or
2. Explicitly confirm the deferral is acceptable for this milestone and keep the
   docstring note added in commit d48b0e0.

Add a nested-sub-model SF fixture + test either way.
