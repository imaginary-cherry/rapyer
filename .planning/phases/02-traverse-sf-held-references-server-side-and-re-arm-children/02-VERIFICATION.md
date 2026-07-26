---
phase: 02-traverse-sf-held-references-server-side-and-re-arm-children
verified: 2026-07-26T00:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 2: Traverse SF-held references server-side and re-arm children — Verification Report

**Phase Goal:** When a cascade fires on a parent (asave, aset_ttl(cascade=True), refresh_ttl), the server-side traversal reads each cascade-enabled RedisSet / RedisPriorityQueue key, follows every ForeignKey reference found there, and re-arms each reached child to its own Meta.ttl — atomically, cycle-safely, in the same operation as inline-reached children, with the apply layer reused unchanged. This includes the model-level cascade-trigger gate: asave/aset_ttl/refresh_ttl must actually invoke the cascade Function for parents whose ONLY cascade edge is SF-held.

**Verified:** 2026-07-26
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A cascade on a `RedisSet[ForeignKey[T]]` parent re-arms every set-member child to its own `Meta.ttl`, server-side, atomic, same op as inline children | ✓ VERIFIED | `rapyer/scripts/lua/cascade/library.lua:229-252` (`push_sf_edge`, SMEMBERS branch); proven by `test_cascade_sf_held_ref_apply.py::test_set_ref_parent_reaches_and_refreshes_both_set_members` (real Redis :6370, passing) |
| 2 | A cascade on a `RedisPriorityQueue[ForeignKey[T]]` parent re-arms every ZSET-member child likewise | ✓ VERIFIED | `library.lua:241-242` (ZRANGE branch); proven by `test_pq_ref_parent_reaches_and_refreshes_pq_member` |
| 3 | Reach holds through the PUBLIC API (asave, aset_ttl(cascade=True), refresh_ttl), not only direct FCALL | ✓ VERIFIED | `rapyer/base.py:248-267` (`_has_cascade_enabled_sf_ref_edge` + `_contains_foreign_key` OR-fix); `test_cascade_sf_held_ref_public_api.py` — 3 tests (`asave()` x2, `aset_ttl(cascade=True)` x1) against real Redis :6370, zero `fcall`/`_apply_cascade` calls in the file (grep confirms 0 matches) |
| 4 | Model-level trigger gate: parents whose ONLY cascade edge is SF-held actually invoke the cascade Function | ✓ VERIFIED | `rapyer/cascade/planner.py` `class_declares_cascade_enabled_sf_ref_edge`; `test_cascade_sf_only_trigger_gate.py` (mock-based, `run_fcall` called for `CascadeSetRefParent`/`CascadePQRefParent`, `pipe.expire` for cascade-disabled `CascadeSetRefOptOut`) |
| 5 | Traversal through SF containers is cycle-safe (shared visited/best-budget-per-node) — mixed inline+SF diamonds, SF-only dual-edge diamonds, shared inline+SF children, self-refs in SET/PQ all terminate and re-arm correctly | ✓ VERIFIED | Shared `visited`/`push_child`/`budget_is_larger` machinery (`library.lua:118-132, 204-224`) reused verbatim for SF edges; proven by Tests D (self-ref SET), E (mixed-edge max-budget-wins), G (self-ref PQ), H (SF-only dual-edge diamond, `result == [0,0]`) — all pass on real Redis |
| 6 | Existing behavior preserved: inline FK cascade shapes, Meta.ttl/refresh_ttl, non-cascade models unchanged; prior regression suites pass unmodified | ✓ VERIFIED | `git diff e2ac3e2 HEAD -- tests/integration/foreign_keys/test_cascade_graph_shapes.py tests/integration/foreign_keys/test_cascade_depth_and_gate.py` = 0 lines; both files pass; `contains_fk_field()`/`__init_subclass__` byte-for-byte unmodified (confirmed via diff); full `tests/unit/` (818 passed) and `tests/integration/` (1623 passed / 205 skipped) suites green |
| 7 | Dual test strategy: fakeredis (unit) + real Redis Stack :6370 (integration), honoring documented divergence | ✓ VERIFIED | `tests/unit/cascade/test_cascade_sf_held_ref_fakeredis_fallback.py` (2 tests, real non-mocked fakeredis, proves root+container refresh, member untouched) + `tests/integration/foreign_keys/test_cascade_sf_held_ref_apply.py` (8 tests) + `test_cascade_sf_held_ref_public_api.py` (3 tests), all passing against real Redis :6370 |
| 8 | TTL Cascade documentation states SF-held references participate in cascade, with coverage matrix for the two new shapes | ✓ VERIFIED | `docs/documentation/special-fields/ttl-cascade.md:74-131` — "Cascade-Eligible Shapes" section, 5-row coverage matrix, worked `RedisSet[Reference[Author]]` example, extended fakeredis-divergence note (lines 21-24) |
| 9 | Malformed/non-JSON or non-string-decoded SF members do not crash the atomic FCALL and are simply skipped | ✓ VERIFIED | `library.lua:247-250` (`pcall(cjson.decode, raw_member)` + `type(target_key) == 'string'` guard); proven by Test F (`test_malformed_and_non_string_sf_members_are_tolerated`, injects `"not-json"` and `"42"` directly via `sadd`, passes) |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `rapyer/scripts/lua/cascade/library.lua` | `push_edges` SF-container read branch (SMEMBERS/ZRANGE), reusing push_child/next_hop/visited | ✓ VERIFIED | `push_sf_edge` (lines 229-252) + branch in `push_edges` (lines 268-277); inline `JSON.GET` batch only ever receives non-SF edges (`inline_edges` list) |
| `rapyer/cascade/planner.py` | `class_declares_cascade_enabled_sf_ref_edge`, reusing `_static_walk_sf_fk_edges` classification | ✓ VERIFIED | Lines ~269-282; thin wrapper, no duplicated classification logic |
| `rapyer/base.py` | `_has_cascade_enabled_sf_ref_edge()` lazily-cached classmethod + `_contains_foreign_key()` OR-fix | ✓ VERIFIED | Lines 248-267; `git diff e2ac3e2 HEAD -- rapyer/base.py` shows an isolated, minimal 14-line addition |
| `tests/models/cascade_types.py` | Six new hard-shape fixtures registered in `ALL_CASCADE_MODELS` | ✓ VERIFIED | `CascadeSetRefSelfNode`, `CascadePQRefSelfNode`, `CascadeMixedEdgeSharedChild(Root)`, `CascadeSfDiamondChild`/`Root` all present and registered (lines 401-524) |
| `tests/integration/foreign_keys/test_cascade_sf_held_ref_apply.py` | 8 tests (A-H), direct FCALL proof | ✓ VERIFIED | 8 test functions present, all pass against real Redis :6370 |
| `tests/integration/foreign_keys/test_cascade_sf_held_ref_public_api.py` | 3 tests (A-C), public-API-only proof | ✓ VERIFIED | 3 test functions, zero fcall/_apply_cascade references, all pass |
| `tests/unit/cascade/test_cascade_sf_held_ref_fakeredis_fallback.py` | 2 tests, fakeredis fallback proof | ✓ VERIFIED | 2 test functions, no mocking, both pass |
| `tests/unit/cascade/test_cascade_sf_only_trigger_gate.py` | 3 tests, mock-based gate proof | ✓ VERIFIED | 3 test functions, all pass |
| `docs/documentation/special-fields/ttl-cascade.md` | Coverage matrix + worked example + divergence note | ✓ VERIFIED | Section present, 5-row matrix, worked example, divergence note extended |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `library.lua push_edges` | SF container Redis key (SMEMBERS/ZRANGE) | `special_prefix .. ':' .. parent_key .. ':' .. edge.path`, branched on `edge.sf_container` | ✓ WIRED | `library.lua:237-242` |
| `library.lua push_sf_edge` | `push_child` | `cjson.decode(raw_member)` then `push_child(target_key, edge, budget)` | ✓ WIRED | `library.lua:247-250` |
| `rapyer/base.py _contains_foreign_key` | `rapyer/cascade/planner.class_declares_cascade_enabled_sf_ref_edge` | classmethod call, result lazily cached on `cls.__dict__` | ✓ WIRED | `base.py:249-267`; lazy import breaks a real init-time cycle (documented as an auto-fixed deviation, verified via `uv run python -c "import rapyer.base"` and full suite) |
| `test_cascade_sf_held_ref_public_api.py` | `CascadeSetRefParent.asave()` / `aset_ttl(cascade=True)` | public API call only | ✓ WIRED | Confirmed via source read + passing test run; `grep -c "fcall\|_apply_cascade"` == 0 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CASF-04 | 02-01, 02-04 | RedisSet traversal + public API trigger | ✓ SATISFIED | Direct-FCALL proof (02-01) + public-API proof (02-04) both pass |
| CASF-05 | 02-01, 02-04 | RedisPriorityQueue traversal + public API trigger | ✓ SATISFIED | Same, PQ-shaped tests pass |
| CASF-06 | 02-01, 02-04 | Per-child re-arm atomic, same op as inline, no TOCTOU | ✓ SATISFIED | Single FCALL write-phase EXPIRE loop unchanged; dangling reuse (Test C) confirms shared apply layer |
| CASF-07 | 02-01 | Cycle-safety, depth budget, diamonds, self-refs | ✓ SATISFIED | Tests D, E, G, H all pass |
| CASF-08 | 02-01 | Byte-for-byte preservation of existing behavior | ✓ SATISFIED | Zero diff on regression test files; full suite green |
| CASF-09 | 02-01, 02-02 | Dual test strategy (fakeredis + real Redis) | ✓ SATISFIED | Both legs proven and passing |
| CASF-10 | 02-03 | Documentation coverage matrix + worked example | ✓ SATISFIED | `ttl-cascade.md` updated as described |

No orphaned requirements — all of CASF-04 through CASF-10 are claimed by at least one plan's frontmatter `requirements:` field and independently verified above.

**Note (informational, non-blocking):** `.planning/REQUIREMENTS.md`'s checkbox list and traceability table still show CASF-04 through CASF-10 as `[ ]` Pending, even though the underlying code and tests prove them satisfied. This appears to be a tracking-document update that is deferred to milestone-end rather than a per-phase step (Phase 1's CASF-01..03 rows are marked `[x]` Complete in the same file, suggesting this update happens as part of milestone closure). This does not affect the codebase-truth verification above and is not treated as a gap.

### Anti-Patterns Found

None. Scanned all modified/created files (`library.lua`, `planner.py`, `base.py`, `redis_set.py`, `priority_queue.py`, `cascade_types.py`, all 4 new test files, `ttl-cascade.md`) for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`/"not yet implemented" — one incidental match in `ttl-cascade.md` line 192 is prose explicitly clarifying something is *not* a gap (unrelated standalone-Redis design note), not a debt marker.

### Behavioral Spot-Checks / Test Execution

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit cascade suite | `uv run pytest tests/unit/cascade/ -q` | 80 passed | ✓ PASS |
| New + regression real-Redis integration | `uv run pytest tests/integration/foreign_keys/test_cascade_sf_held_ref_apply.py tests/integration/foreign_keys/test_cascade_sf_held_ref_public_api.py tests/integration/foreign_keys/test_cascade_graph_shapes.py tests/integration/foreign_keys/test_cascade_depth_and_gate.py -q` | 27 passed | ✓ PASS |
| Full unit suite (regression) | `uv run pytest tests/unit/ -q` | 818 passed | ✓ PASS |
| Full integration suite (regression) | `uv run pytest tests/integration/ -q` | 1623 passed, 205 skipped | ✓ PASS |

(Real Redis Stack confirmed reachable on :6370 via `redis-cli -p 6370 ping` → `PONG`. Unit and integration suites run in separate `uv run pytest` invocations per the known fixture-leak constraint.)

### Human Verification Required

None. All must-haves are verified programmatically via source inspection and passing automated test runs against both fakeredis and real Redis Stack :6370.

### Gaps Summary

No gaps. All 9 derived observable truths verified, all 9 required artifacts present/substantive/wired, all 4 key links wired, all 7 requirement IDs (CASF-04..10) satisfied with test evidence, zero anti-patterns, zero regressions across 818 unit + 1623 integration tests.

---

_Verified: 2026-07-26_
_Verifier: Claude (gsd-verifier)_
