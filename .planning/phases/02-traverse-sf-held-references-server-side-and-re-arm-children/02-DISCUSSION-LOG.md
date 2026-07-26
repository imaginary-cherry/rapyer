# Phase 2: Traverse SF-held references server-side and re-arm children - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-25
**Phase:** 2-traverse-sf-held-references-server-side-and-re-arm-children
**Areas discussed:** fakeredis reach coverage, Dangling/missing SF members, Divergence observability, Docs coverage-matrix depth

**Framing:** Most of Phase 2 was already locked by Phase 1 (edge shape `sf_container` in `entry.fks`, depth `is_collection=True`/one hop, best-budget-per-node cycle-safety) + v1.3.5 backbone (per-child own-`Meta.ttl` EXPIRE apply, real-Redis-Function path + fakeredis root-own fallback, `SMEMBERS`/`ZRANGE` read commands). Discussion focused only on the genuinely-open decisions. All four resolved to the recommended (default-preserving) option.

---

## fakeredis reach coverage (CASF-09)

| Option | Description | Selected |
|--------|-------------|----------|
| A. Status-quo fallback | Function real-only; fakeredis stays root-own. Reach proven on real Redis :6370; fakeredis unit tests assert the fallback + Phase-1 static plan tests cover classification. One source of truth in Lua. | ✓ |
| B. Python-side fallback traversal | Add a Python traversal so fakeredis also cascades children — hermetic unit proof but duplicates cycle/budget logic in Python (divergence risk, more surface). | |

**User's choice:** A. Status-quo fallback
**Notes:** Keeps the milestone honest (traversal-reach in Lua, single source of truth), consistent with the v1.3.5 documented fakeredis/real-Redis divergence and the roadmap wording. Verified in `init.py:92-101` that the Function is `not is_fake_redis`-gated, so inline cascade already doesn't run on fakeredis — SF stays consistent.

---

## Dangling/missing SF members

| Option | Description | Selected |
|--------|-------------|----------|
| A. Reuse existing dangling-count | SF members ride the same `push_child`→EXPIRE-no-op path; counted in `dangling_children_count`. Zero new logic. | ✓ |
| B. Separate SF-dangling counter | Distinguish SF-held dangling from inline dangling in the result — new return field rippling to `CascadeResult`. | |

**User's choice:** A. Reuse existing dangling-count
**Notes:** Verified `library.lua:323-345` — a missing reached child's key makes EXPIRE a cheap no-op and is already tallied. SF members flow through the identical write phase.

---

## Divergence observability

| Option | Description | Selected |
|--------|-------------|----------|
| A. Silent no-op | Consistent with how inline cascade already behaves on fakeredis (no Function loaded); divergence documented in CASF-10 docs. | ✓ |
| B. One init-time debug log | Emit a single debug log when cascade-enabled models init against fakeredis, so the no-reach divergence is visible in dev/tests. | |

**User's choice:** A. Silent no-op
**Notes:** Consistency with existing inline-cascade fakeredis behavior beats a warning; the divergence is surfaced via documentation (D-04 / CASF-10) instead of runtime noise.

---

## Docs coverage-matrix depth (CASF-10)

| Option | Description | Selected |
|--------|-------------|----------|
| B. Matrix + example + divergence note | Coverage matrix + docstrings PLUS a worked RedisSet/PQ cascade example and the fakeredis divergence note — matches existing v1.3.5 cascade docs style. Low extra cost. | ✓ |
| A. Matrix + docstrings only | The literal CASF-10 minimum: add the two new shapes to the coverage matrix and update docstrings, no worked example. | |

**User's choice:** B. Matrix + example + divergence note
**Notes:** A worked example materially helps users adopt a non-obvious feature; low cost and mirrors the existing cascade docs.

## Claude's Discretion

- Exact Lua structure for interleaving the SF read (inline in `push_edges` vs a dedicated `edge.sf_container` branch), provided members reach the same `push_child`/`next_hop`/`visited` machinery and the inline single-`JSON.GET` batch is preserved.
- Member decode details (`SMEMBERS`/`ZRANGE` returning plain target-key strings; byte-vs-str shape per backend).
- Integration-test graph fixture naming/selection on :6370, provided they cover the enumerated hard shapes.
- ZSET read form (`ZRANGE key 0 -1`) and large-container concerns.

## Deferred Ideas

- Python-side fallback traversal for fakeredis (rejected D-01a) — revisit only if hermetic unit coverage of reach becomes required.
- Separate SF-dangling counter / distinct SF-hop error subtype (D-02; Phase 1 D-04a) — unless the generic count/message proves confusing.
- SF containers holding nested inline submodels — out of milestone scope (REQUIREMENTS "Future").
- Save/update/delete cascade apply through SF-held refs — out of milestone scope (traversal-reach only).
