# Phase 1: Classify SF-held FK references into the cascade plan - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-24
**Phase:** 1-classify-sf-held-fk-references-into-the-cascade-plan
**Areas discussed:** Edge representation, Discovery path, Depth & collection semantics, Fail-fast validation
**Mode:** advisor (standard tier; NON_TECHNICAL_OWNER=false) — four parallel grounded researchers produced comparison tables; presented consolidated, user locked the recommended set.

---

## Edge representation

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Discriminator on `CascadeEdge`, same `fks` list | `sf_container: "set"\|"zset"\|None` + key-suffix; None serializes away → plan-hash stable; validation free; reuses all hooks | ✓ |
| (b) Separate `sf_fk_edges` list on `CascadePlanEntry` | Keeps `JSON.GET` batch pristine, but forces validator extension + duplicate traversal wiring | |
| (c) Overload `special_suffixes` into objects | Breaks "suffixes are EXPIRE'd, never followed" invariant the milestone forbids changing | |

**User's choice:** (a)
**Notes:** Verified defect basis — SF-held FKs are unreachable via `JSON.GET` since members live under a separate SET/ZSET key; cost of not joining the batch is intrinsic to storage layout and paid under every option.

---

## Discovery path

| Option | Description | Selected |
|--------|-------------|----------|
| (b) Dedicated planner pass over `_special_field_names` | Filter to fields where `_unwrap_relational_target` ≠ None; zero `base.py` edits; reuses existing target-unwrap | ✓ |
| (c) New `_sf_fk_field_names` in `__init_subclass__` | Tidy but edits the fragile classifier, process-wide blast radius, no Phase-1 benefit | |
| (a) Redirect `_contain_fk` collection branch | Non-viable — verified the field is never in `_contain_fk` (`contains_fk_field()` → False for SF types) | |

**User's choice:** (b)
**Notes:** Key verified fact — `contains_fk_field()` returns False for `RedisSet`/`RedisPriorityQueue` (only `GenericRedisType` overrides); today these fields emit a refresh-only suffix but no edge at all.

---

## Depth & collection semantics

| Option | Description | Selected |
|--------|-------------|----------|
| A. Mirror collection-of-FK (`is_collection=True`) | One edge per SF field, all members share one budget; `depth=N` counts hops like inline `list[FK]`; visited/cycle logic reused unchanged | ✓ |
| B. Two-level budget (container hop + member hop) | Contradicts the inline-collection mental model; surprising self-ref depth math | |
| C. Overload `is_collection`, infer SF source at runtime | Pushes SF-type lookup into the hot Lua path; fragile path↔suffix derivation | |

**User's choice:** A
**Notes:** `push_child`/best-budget-per-node map keys on the target-key string, so inline+SF dual-reachable children and self-refs-in-set dedup/terminate with no new reasoning.

---

## Fail-fast validation

| Option | Description | Selected |
|--------|-------------|----------|
| A. Reuse `entry.fks` + `CascadeTargetTtlMissingError` as-is | Validator is edge-representation-agnostic; SF targets covered free; only a regression test needed | ✓ |
| B. Separate list + extend validator | Only needed if edge-repr used a separate list (it doesn't); adds cross-list ordering + root-check risk | |
| C. Distinct SF-hop error message/subtype | Orthogonal diagnostics layer; deferred — `edge.path` already localizes the field | |

**User's choice:** A (distinct error message deferred)
**Notes:** Fully coupled to Edge-representation = (a); keeping SF edges in `fks` is what makes validation free.

---

## Claude's Discretion

- Exact `CascadeEdge` field names and whether the SF key suffix reuses the `special_suffixes` string form (D-01/D-01a/D-01b must hold).
- Precise shape of Phase-1 unit assertions (plan-dict vs plan-JSON), provided they prove the new edge shape, None-drop for non-SF models, precedence, and the fail-fast case.

## Deferred Ideas

- Phase 2: server-side `library.lua` traversal (SMEMBERS/ZRANGE + follow + re-arm) — CASF-04..10.
- Distinct "reached via RedisSet/PriorityQueue field" fail-fast error message/subtype.
- SF containers holding nested inline submodels (vs direct `ForeignKey[T]`) — milestone "Future".
- Save/update/delete cascade apply through SF-held refs — out of milestone scope.
