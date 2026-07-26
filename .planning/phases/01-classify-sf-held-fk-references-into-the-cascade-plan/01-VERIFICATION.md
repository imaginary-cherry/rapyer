---
phase: 01-classify-sf-held-fk-references-into-the-cascade-plan
verified: 2026-07-24T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 1: Classify SF-held FK references into the cascade plan Verification Report

**Phase Goal:** The static cascade plan recognizes SF-held `ForeignKey` references (`RedisSet[ForeignKey[T]]`, `RedisPriorityQueue[ForeignKey[T]]`) as their own cascade edge shape — the exact data the server-side traversal will consume — via pure annotation introspection with zero Redis I/O.
**Verified:** 2026-07-24
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A user can declare `RedisSet[Reference[T]]` / `RedisPriorityQueue[Reference[T]]` fields; FK elements recognized via a dedicated pass over `_special_field_names` (D-02) | VERIFIED | `rapyer/cascade/planner.py:198-237` — `_static_walk_sf_fk_edges` iterates `model_cls._special_field_names`, resolves target via `_unwrap_relational_target`, classifies container kind via `safe_issubclass(origin, RedisSet/RedisPriorityQueue)`. `base.py` untouched (diff empty, verified below). Tests `test_set_held_ref_produces_one_edge_marked_set`, `test_pq_held_ref_produces_one_edge_marked_zset_with_depth` pass. |
| 2 | `build_cascade_plan` emits a distinct SF-held-ref edge (`sf_container="set"/"zset"`) recording SF key suffix, target class, depth — separate from inline FK edges and from `special_suffixes` | VERIFIED | Live check: `build_cascade_plan([CascadeSetRefParent, CascadeAuthor])` → `cascade_plan_json` produces `{'path': 'refs', 'target': 'CascadeAuthor', 'is_collection': True, ..., 'sf_container': 'set'}` in `fks`, plus independently `'special_suffixes': ['refs']` — both present, distinct mechanisms. Confirms D-01/D-01b/D-02b. |
| 3 | Cascade enables via per-field `CascadeTTL` or global blanket, honoring field > global > off precedence identically to inline FK fields | VERIFIED | `_classify_edge` (shared helper, unmodified) reused verbatim in the new pass. `test_blanket_global_enables_sf_edge_with_global_depth` (global blanket → edge with depth=2) and `test_field_opt_out_beats_enabled_global_and_emits_no_sf_edge` (field opt-out beats enabled global → zero edges) both pass. |
| 4 | A cascade-enabled SF-held-ref target with `Meta.ttl=None` fails fast (`CascadeTargetTtlMissingError`), including root-with-only-SF-edges | VERIFIED | `test_sf_held_ref_target_with_no_ttl_fails_fast` (target violation, `model_name == "CascadeSetRefNoTtlTarget"`) and `test_root_with_only_sf_edges_and_no_ttl_fails_fast` (root violation, `model_name == "CascadeSetRefRootNoTtl"`) both pass. `validate_cascade_ttl_targets` source unmodified (D-04) — SF edges ride the same `entry.fks` list. |
| 5 | Non-SF plan bytes/hash byte-identical (`sf_container=None` dropped); pre-existing cascade tests pass unmodified | VERIFIED | `test_non_sf_edge_json_has_no_sf_container_key` passes. Full `tests/unit/cascade` suite: 75 passed. `tests/unit/cascade/test_cascade_plan_table.py` + `test_cascade_ttl_required_validation.py`: 23 passed, files unmodified in diff. Full `tests/unit`: 813 passed. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `rapyer/cascade/planner.py` | `CascadeEdge.sf_container` discriminator + dedicated SF discovery pass wired into `build_cascade_plan` | VERIFIED | `sf_container: str | None = None` is the last field (line 77), field order preserved. `_static_walk_sf_fk_edges` (line 198) called from `build_cascade_plan` (line 284) immediately after `_static_walk_fk_edges`, appending to the same `fks` list. |
| `tests/models/cascade_types.py` | SF-held-ref test fixtures (set + zset; per-field, blanket, opt-out; missing-ttl target; root-with-only-SF-edges) | VERIFIED | 7 fixtures present (lines 319-395): `CascadeSetRefParent`, `CascadePQRefParent`, `CascadeSetRefBlanket`, `CascadeSetRefOptOut` (ttl-carrying, in `ALL_CASCADE_MODELS`/`CASCADE_PLANNER_MODELS`), `CascadeSetRefNoTtlTarget`, `CascadeSetRefToNoTtl`, `CascadeSetRefRootNoTtl` (ttl-less, `init_with_rapyer=False`, correctly excluded from both lists). |
| `tests/unit/cascade/test_cascade_sf_held_ref_plan.py` | Unit assertions on edge shape, precedence, None-drop hash stability, fail-fast validation | VERIFIED | 11 tests present and passing (SUMMARY.md claims 12 — minor narrative discrepancy, no functional impact; see Anti-Patterns/Notes). Covers every item in the plan's `<behavior>` block. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| SF discovery pass | `_unwrap_relational_target` | target-class resolution over `_special_field_names` annotations | WIRED | `planner.py:211` `target_cls = _unwrap_relational_target(annotation)`, reused verbatim, no new resolution logic. |
| SF discovery pass | `_classify_edge` | field > global > off precedence for enabled/depth/override | WIRED | `planner.py:222` `edge = _classify_edge(model_cls, field_name)`; skip when `not edge.enabled`. |
| SF-held-ref `CascadeEdge` | `entry.fks` | appended to same list so `validate_cascade_ttl_targets` covers SF targets unchanged | WIRED | `planner.py:225` `fks.append(CascadeEdge(...))` inside `_static_walk_sf_fk_edges`, called with the same `fks` list `build_cascade_plan` passes to `_static_walk_fk_edges`. |
| `CascadeEdge.sf_container=None` | `_drop_none_values` | None discriminator serializes away for non-SF edges | WIRED | Live-verified: `cascade_plan_json` output for `CascadeSetRefParent` has `sf_container` present when set; `test_non_sf_edge_json_has_no_sf_container_key` proves absence for non-SF edges. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CASF-01 | 01-01-PLAN.md | User can declare SF-held-ref field (RedisSet/RedisPriorityQueue of ForeignKey) | SATISFIED | Fixtures + `_static_walk_sf_fk_edges` recognize both container types; tests pass. |
| CASF-02 | 01-01-PLAN.md | Cascade enable via per-field CascadeTTL or global default, field > global > off precedence | SATISFIED | `_classify_edge` reused; blanket + opt-out tests pass. |
| CASF-03 | 01-01-PLAN.md | `build_cascade_plan` classifies SF-held-ref fields into a distinct edge shape (suffix, target, depth) | SATISFIED | `sf_container` discriminator + dedicated pass; edge-shape tests pass; distinct from `special_suffixes`. |

REQUIREMENTS.md traceability table maps CASF-01/02/03 to Phase 1 (status: Complete) and CASF-04..10 to Phase 2 (Pending) — no orphaned requirement IDs for this phase; PLAN frontmatter `requirements: [CASF-01, CASF-02, CASF-03]` matches exactly.

### Anti-Patterns Found

None. Scanned all 4 modified/created files (`rapyer/cascade/planner.py`, `tests/models/cascade_types.py`, `tests/unit/cascade/conftest.py`, `tests/unit/cascade/test_cascade_sf_held_ref_plan.py`) for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` and stub patterns — zero matches. `black --check` and `ruff check` both pass clean on all modified files.

**Note (non-blocking):** SUMMARY.md claims "12 new unit tests" in `test_cascade_sf_held_ref_plan.py`; actual count is 11 (verified via `grep -c "^def test_"` and pytest collection). Cosmetic discrepancy only — every behavior the plan's `<behavior>` block requires is covered by the 11 tests, all passing.

### Regression Checks (as requested)

| Check | Result |
|-------|--------|
| `uv run pytest tests/unit/cascade -q` | 75 passed |
| `uv run pytest tests/unit -q` (full suite) | 813 passed |
| `rapyer/base.py` diff (HEAD~2..HEAD) | 0 lines — empty |
| `git diff --name-only HEAD~2 HEAD` | `rapyer/cascade/planner.py`, `tests/models/cascade_types.py`, `tests/unit/cascade/conftest.py`, `tests/unit/cascade/test_cascade_sf_held_ref_plan.py` — no Lua files, matches plan's declared file scope exactly |
| Non-SF plan bytes unaffected | `test_non_sf_edge_json_has_no_sf_container_key` passes; `sf_container` key absent from non-SF edge JSON via `_drop_none_values` |
| `black --check` / `ruff check` on modified files | Both clean |

### Human Verification Required

None. This phase is pure in-process annotation introspection (no UI, no network, no Redis I/O, no external service) — fully verifiable via unit tests and direct code inspection. All must-haves resolved programmatically.

### Gaps Summary

No gaps. All 5 derived observable truths (from ROADMAP success criteria + PLAN frontmatter must-haves, merged with the roadmap contract taking precedence) are VERIFIED against actual codebase behavior, not just SUMMARY.md narrative. The edge shape was independently re-derived by running `build_cascade_plan` live in this verification session (not by trusting test assertions alone), confirming the exact JSON payload: `sf_container`, dotted `path` (no `$.` prefix), `is_collection=True`, target class name, and correct None-drop behavior for depth. `base.py` and all Lua files are untouched per diff inspection. Full unit suite (813 tests) passes with zero regressions.

---

*Verified: 2026-07-24*
*Verifier: Claude (gsd-verifier)*
