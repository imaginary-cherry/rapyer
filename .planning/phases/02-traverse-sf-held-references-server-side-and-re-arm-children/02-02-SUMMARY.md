---
phase: 02-traverse-sf-held-references-server-side-and-re-arm-children
plan: 02
subsystem: testing
tags: [cascade, ttl, fakeredis, redis-set, redis-priority-queue, foreign-key]

# Dependency graph
requires:
  - phase: 01-classify-sf-held-fk-references-into-the-cascade-plan
    provides: sf_container discriminator on CascadeEdge, SF-held-ref fixtures (CascadeSetRefParent, CascadePQRefParent) registered in CASCADE_PLANNER_MODELS
provides:
  - Fakeredis-leg proof for CASF-09 (dual-backend requirement): SF-held-ref cascade-enabled models never invoke the cascade Function on fakeredis, and correctly fall back to refreshing only their own keys (main + SF container)
affects: [02-01 (real-Redis Function-path leg of CASF-09), 02-03, 02-04, CASF-10 docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "End-to-end fakeredis-fallback proof mirrors test_aset_ttl_cascade_flag.py's existing pattern: real (non-mocked) fakeredis client, real aset_ttl(cascade=True) call, persist() to isolate the assertion to the call's own TTL side effects"

key-files:
  created:
    - tests/unit/cascade/test_cascade_sf_held_ref_fakeredis_fallback.py
  modified: []

key-decisions:
  - "SF-held-ref FK members must be passed to .aadd()/.apush() as an already-constructed ForeignKey instance (not a bare key string): RedisSet/RedisPriorityQueue's _dump_member(s) calls the TypeAdapter's dump_python (serialization only, no validation), and ForeignKey's core-schema serializer assumes the value already has a _target_key attribute. Passing a plain str/RapyerKey raises PydanticSerializationError. This differs from direct/collection Reference fields (list[Reference[T]]), which go through pydantic validation on model-construction assignment and so accept a plain key string."

requirements-completed: [CASF-09]

duration: 4min
completed: 2026-07-26
---

# Phase 2 Plan 2: Fakeredis Fallback Proof for SF-Held-Ref Cascade Summary

**Proved, with two real (non-mocked) fakeredis end-to-end tests, that CascadeSetRefParent and CascadePQRefParent never invoke the cascade Redis Function on fakeredis and instead refresh only their own keys (main + SF container) via the pre-existing root-own-EXPIRE fallback, leaving the SF container's FK member untouched.**

## Performance

- **Duration:** ~4 min
- **Completed:** 2026-07-26
- **Tasks:** 2/2 completed
- **Files modified:** 1 (created)

## Accomplishments

- Added `tests/unit/cascade/test_cascade_sf_held_ref_fakeredis_fallback.py` with two tests proving the fakeredis fallback contract for both SF container kinds Phase 1 classified: `RedisSet` (SET) and `RedisPriorityQueue` (ZSET).
- Each test: saves an author, saves an SF-held-ref parent, adds the author's key into the parent's SF container, `persist()`s all three keys to isolate the assertion window, calls `aset_ttl(TTL, cascade=True)`, then asserts the parent's main key and the SF container's own key got a positive TTL while the author's key stayed persisted (`ttl in (-1, -2)`) — proving no traversal into the container's members occurred.
- Confirmed `result == CascadeResult(dangling_children=0, dangling_special=0)` — the fast path's fixed return value.
- Ran the full `tests/unit/cascade/` suite (77 tests) to confirm zero regression from the new file.

## Task Commits

Each task was committed atomically:

1. **Task 1: Fakeredis fallback proof for CascadeSetRefParent (RedisSet)** - `5b72280` (test)
2. **Task 2: Fakeredis fallback proof for CascadePQRefParent (RedisPriorityQueue)** - `14a1925` (test)

_Note: no separate plan-metadata commit — this SUMMARY commit is the metadata commit (parallel-worktree execution; orchestrator owns STATE.md/ROADMAP.md updates after merge)._

## Files Created/Modified

- `tests/unit/cascade/test_cascade_sf_held_ref_fakeredis_fallback.py` - Two fakeredis end-to-end tests proving the CASF-09 fallback contract for RedisSet- and RedisPriorityQueue-shaped SF-held-ref parents.

## Decisions Made

- **`ForeignKey`-wrap requirement for SF mutators, discovered during Task 1 implementation:** `RedisSet.aadd()` / `RedisPriorityQueue.apush()` bypass pydantic's validate-on-assignment path that direct/collection `Reference[T]` fields get; they call `_dump_member(s)`, which invokes the field's `TypeAdapter.dump_python` (serialize-only). `ForeignKey`'s pydantic core-schema serializer (`rapyer/types/foreign_key.py::_serialize`) assumes its input is already a `ForeignKey` instance and reads `value._target_key` unconditionally. Passing a bare key string (even a `RapyerKey`) raises `PydanticSerializationError: 'RapyerKey' object has no attribute '_target_key'`. Both tests construct `ForeignKey(author.key)` explicitly before calling `.aadd()`/`.apush()`. No production code was touched — this is a test-authoring detail specific to constructing SF-held-ref fixtures directly (as opposed to via a saved parent's constructor, which does validate).

## Deviations from Plan

None — plan executed exactly as written. The one non-trivial discovery (the `ForeignKey`-wrap requirement above) was resolved entirely within the test file per the plan's own "Claude's Discretion" latitude for member-decoding details; no production code in `rapyer/base.py` or elsewhere was modified, consistent with the plan's explicit scope boundary (test-only, D-01/D-01a).

## TDD Gate Compliance

Both tasks are marked `tdd="true"` in the plan, but the plan's objective explicitly frames this work as "a test-only proof of an already-correct, already-gated code path" — the fakeredis fast path in `aset_ttl`/`refresh_ttl` is pre-existing, unmodified production code (`self.Meta.is_fake_redis or ...` short-circuit in `rapyer/base.py`). There is no GREEN implementation step because no production code changes; both tests passed on first write against the existing code path, matching the plan's own prediction ("already-gated... short-circuits before the model-level cascade-enablement gate is ever consulted"). This is a deliberate proof-test rather than a bug-fixing RED→GREEN cycle, so both tasks were committed as single `test(...)` commits rather than split `test`/`feat` pairs.

## Verification Evidence

- `uv run pytest tests/unit/cascade/test_cascade_sf_held_ref_fakeredis_fallback.py -x` — 2 passed.
- `uv run pytest tests/unit/cascade/ -q` — 77 passed (full suite regression check, per the plan's `<verification>` block).
- Neither test uses `unittest.mock` — confirmed by manual inspection of the file (no `mock` import).

## Self-Check: PASSED

- FOUND: tests/unit/cascade/test_cascade_sf_held_ref_fakeredis_fallback.py
- FOUND: 5b72280 (test(02-02): fakeredis fallback proof for CascadeSetRefParent)
- FOUND: 14a1925 (test(02-02): fakeredis fallback proof for CascadePQRefParent)
