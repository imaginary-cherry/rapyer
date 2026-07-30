---
gsd_state_version: 1.0
milestone: v1.3.6
milestone_name: Cascade Reach Through Special-Field References
status: milestone_complete
stopped_at: Milestone complete (Phase 02 was final phase)
last_updated: 2026-07-25T22:40:50.952Z
last_activity: 2026-07-25 -- Phase 02 execution started
progress:
  total_phases: 2
  completed_phases: 1
  total_plans: 5
  completed_plans: 5
  percent: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-24)

**Core value:** Give Redis users a genuine relational-ORM experience — the cascade/TTL/referential-integrity behaviors people expect from an RDBMS. This isolated milestone extends the v1.3.5 TTL cascade so the shared walker also discovers `ForeignKey` references held *inside* special-field containers (`RedisSet[ForeignKey[T]]`, `RedisPriorityQueue[ForeignKey[T]]`), which live under their own SET/ZSET keys and were never read by the v1.3.5 inline-only (`JSON.GET`) traversal. Traversal-reach only — the per-child cascading-TTL-refresh apply layer is reused unchanged; no new save/update/delete apply action.
**Current focus:** Milestone complete

## Current Position

Phase: 02
Plan: Not started
Status: Milestone complete
Last activity: 2026-07-30

## Quick Tasks Completed

| ID | Task | Date | Status | Commit |
|----|------|------|--------|--------|
| 260730-tv8 | Broaden cascade-refresh gate to fire on any FK or special field (`_needs_cascade_script`) | 2026-07-30 | complete ✓ | b4a63a3 |

## Milestone v1.3.6 Roadmap (SF-Cascade — Phases 1-2)

Traversal-reach only. Build order: Python static classification (unit-verifiable, zero Redis I/O) → server-side Lua traversal + dual-backend proof + docs. Apply layer (cascading-TTL-refresh to each child's own `Meta.ttl`) is reused unchanged from v1.3.5.

| Phase | Name | Requirements | Backend | Notes |
|-------|------|--------------|---------|-------|
| 1 | Classify SF-held FK references into the cascade plan | CASF-01/02/03 | fakeredis-testable (pure introspection) | Extends `_static_walk_fk_edges` / `build_cascade_plan` with a new SF-held-ref edge shape (SF key suffix + target class + depth); precedence field > global > off; fail-fast on missing target `Meta.ttl` |
| 2 | Traverse SF-held references server-side and re-arm children | CASF-04/05/06/07/08/09/10 | fakeredis (fallback) + real Redis Stack :6370 (Function path) | `library.lua` reads SET (`SMEMBERS`) / ZSET (`ZRANGE`) members and follows refs; apply reused; cycle-safe + depth budget; regression preserved; docs |

## Code Seams (verified in source)

- `rapyer/cascade/planner.py` — `_static_walk_fk_edges` currently walks `_relational_field_names` (direct FK) + `_contain_fk` (nested submodels, collection-of-FK) reading refs inline via `JSON.GET`. SF-held-ref fields are the gap. `CascadeEdge`/`CascadePlanEntry` need a new edge shape (or discriminator) marking "read from the SF key via SMEMBERS/ZRANGE" plus the SF key suffix. `_static_walk_special_suffixes` already enumerates SF suffixes for key-refresh (not for following refs) — the new edge is distinct from those.
- `rapyer/scripts/lua/cascade/library.lua` — `push_edges`/`read_reference_paths` read inline refs via `JSON.GET` only. New read path needed: read the SF key (assembled as `special_prefix .. ':' .. key .. ':' .. suffix`) via SMEMBERS/ZRANGE and feed members through the existing `push_child`/`next_hop`/`visited` budget machinery. Write phase (`EXPIRE` to owning class's `Meta.ttl`) reused unchanged.
- `rapyer/init.py` — invokes `build_cascade_plan`; the new edge shape flows through the existing plan-JSON → Lua-literal → `FUNCTION LOAD` pipeline with no new wiring shape.
- Apply layer (`CascadeResult`, EXPIRE loop, dangling-count) reused unchanged.

## Performance Metrics

**Velocity:**

- Total plans completed: 5
- Average duration: - min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 1 | 8min | 8min |
| 2 | TBD | - | - |
| 01 | 1 | - | - |
| 02 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: Phase 01 P01 (8min, 3 tasks, 4 files)
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions (carried from v1.3.5, load-bearing here)

- **Traversal = server-side Lua/Redis Function; apply = per-child own `Meta.ttl`** (relative `EXPIRE`, no GT/NX/XX). The SF-held-ref reach must slot into this same model — read SF members server-side, push through `push_child`, reuse the EXPIRE write phase.
- **Cascade is set-time only** (no expiry-event cascade — an expired parent's data is gone).
- **Real-Redis-7+ Function path; fakeredis root-own-`EXPIRE` fallback.** The SF read path must be proven on both; honor documented fakeredis/real-Redis divergences (CONCERNS.md).
- **Cascade-reachable target must declare `Meta.ttl`** — fail fast at `init_rapyer()` (`CascadeTargetTtlMissingError`); this validation must extend to SF-held-ref targets.
- **`visited` is a best-budget-per-node map, not a boolean set** — the diamond/shared-child fix; SF-reached children must participate in the same map so a child reachable both inline and via an SF container is walked at the larger budget.

### Decisions from Phase 01 Plan 01

- **`sf_container` is the last `CascadeEdge` field, defaulting to `None`** (D-01/D-01a) — dropped by `_drop_none_values`/`cascade_plan_json` so non-SF plan bytes/hash stay identical.
- **`RedisSet`/`RedisPriorityQueue` must be imported lazily inside `_static_walk_sf_fk_edges`, not at module top** — a real import cycle exists (`rapyer.types.priority_queue` → `rapyer.types.special` → `rapyer.scripts.loader` → `rapyer.cascade.planner`) that the plan's interfaces note incorrectly assumed was cycle-safe.
- **The three deliberately ttl=None fail-fast fixtures need `Meta.init_with_rapyer=False`** — `AtomicRedisModel.__init_subclass__` auto-registers every subclass into the global `REDIS_MODELS`, so without this flag they broke unrelated `init_rapyer()` tests.

### Open Decisions to Resolve During Planning

1. **Plan-table representation of the SF-held-ref edge** — new `is_special`/`sf_kind` discriminator field on `CascadeEdge` (SET vs ZSET) plus the SF key suffix, vs a separate edge list on `CascadePlanEntry`. Must round-trip through `cascade_plan_json` / the Lua long-bracket literal cleanly and stay distinct from `special_suffixes` (which drive key-refresh, not ref-following).
2. **Lua SF read command choice** — `SMEMBERS` for SET, `ZRANGE key 0 -1` for ZSET; confirm member decoding matches how `ForeignKey` serializes into the SF key (plain target-key strings) and that both backends return the same shape.
3. **Depth-budget semantics for the SF hop** — whether reaching into an SF container consumes a blanket hop like an inline collection edge does, or is zero-hop like a nested submodel. Align with how `is_collection` edges are budgeted today.

### Pending Todos

- None yet (pre-planning).

### Blockers/Concerns

- **fakeredis SET/ZSET-in-Lua parity** — verify `SMEMBERS`/`ZRANGE` inside a Function/Lua behaves identically enough on fakeredis' fallback path (or that the fallback path re-derives SF members Python-side). Flag for the dual-test phase.
- Prior v1.3.5 advisories retained for reference: cascade-function self-heal deferred to issue #284; WR-02/WR-03 (test freeze-leak / init freeze not exception-safe) open for a future robustness pass.

## Session Continuity

Last session: 2026-07-25T19:48:46.650Z
Stopped at: Phase 2 context gathered
Resume file: .planning/phases/02-traverse-sf-held-references-server-side-and-re-arm-children/02-CONTEXT.md

## Operator Next Steps

- Plan the first phase: `/gsd:plan-phase 1`
