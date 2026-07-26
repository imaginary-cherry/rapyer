# Roadmap: rapyer — Cascade Reach Through Special-Field References (v1.3.6)

## Overview

A focused, traversal-reach-only extension of the v1.3.5 Configurable TTL Cascade. Today the shared cascade walker discovers `ForeignKey` references only where they live *inline* in the parent JSON document (direct FK, collection-of-FK, nested submodel), read server-side via `JSON.GET`. References held *inside* special-field containers (`RedisSet[ForeignKey[T]]`, `RedisPriorityQueue[ForeignKey[T]]`) live under their own SET / ZSET keys and were never read, so their targets never get re-armed. This milestone extends the walker end-to-end — Python classification, the static `build_cascade_plan` table, and the server-side Redis Function — to read those SF keys and follow the refs found there. The apply layer (per-child cascading-TTL-refresh to each child's own `Meta.ttl`) is reused unchanged; no new save/update/delete cascade action is introduced. All v1.3.5 guarantees hold: atomic + server-side at set-time, cycle-safe (visited-set / best-budget-per-node), per-subtree depth budget.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Classify SF-held FK references into the cascade plan** - Detect `RedisSet[ForeignKey[T]]` / `RedisPriorityQueue[ForeignKey[T]]` fields and record them as a distinct SF-held-ref edge shape in the static per-class plan table. (completed 2026-07-24)
- [x] **Phase 2: Traverse SF-held references server-side and re-arm children** - Extend the Redis Function to read SET/ZSET members and follow the refs, re-arming each reached child to its own `Meta.ttl` atomically; proven dual-backend and documented. (completed 2026-07-25)

## Phase Details

### Phase 1: Classify SF-held FK references into the cascade plan
**Goal**: The static cascade plan recognizes SF-held `ForeignKey` references (`RedisSet[ForeignKey[T]]`, `RedisPriorityQueue[ForeignKey[T]]`) as their own cascade edge shape — the exact data the server-side traversal will consume — via pure annotation introspection with zero Redis I/O.
**Depends on**: Nothing (first phase)
**Requirements**: CASF-01, CASF-02, CASF-03
**Success Criteria** (what must be TRUE):
  1. A user can declare `RedisSet[ForeignKey[T]]` and `RedisPriorityQueue[ForeignKey[T]]` fields; their elements persist as the target's key strings under the special field's own SET / ZSET key, never inline in the parent JSON document.
  2. `build_cascade_plan` emits a distinct SF-held-ref edge for a cascade-enabled such field, recording the special-field key suffix, the target class, and the depth budget — separate from the existing inline FK edge shapes and from the plain SF-refresh suffixes.
  3. Cascade enables on an SF-held-ref field via a per-field `CascadeTTL` annotation or the global `init_rapyer(cascade_ttl=...)` default, honoring the same field > global > off precedence as inline FK fields.
  4. A cascade-enabled SF-held-ref target that declares no `Meta.ttl` fails fast at `init_rapyer()` (`CascadeTargetTtlMissingError`), matching inline FK target validation; inline FK edges and non-cascade fields are unchanged in the generated plan.
**Plans**: 1 plan
  - [x] 01-01-PLAN.md — Classify SF-held FK refs (RedisSet/RedisPriorityQueue) into the cascade plan as a distinct sf_container edge; precedence + fail-fast validation, zero Redis I/O

### Phase 2: Traverse SF-held references server-side and re-arm children
**Goal**: When a cascade fires on a parent (`asave`, `aset_ttl(cascade=True)`, `refresh_ttl`), the server-side traversal reads each cascade-enabled `RedisSet` / `RedisPriorityQueue` key, follows every `ForeignKey` reference found there, and re-arms each reached child to its own `Meta.ttl` — atomically, cycle-safely, in the same operation as inline-reached children, with the apply layer reused unchanged. This includes the model-level cascade-trigger gate: `asave`/`aset_ttl`/`refresh_ttl` must actually invoke the cascade Function for parents whose ONLY cascade edge is SF-held, not just prove reach via a direct Function call.
**Depends on**: Phase 1
**Requirements**: CASF-04, CASF-05, CASF-06, CASF-07, CASF-08, CASF-09, CASF-10
**Success Criteria** (what must be TRUE):
  1. A cascade on a parent holding a `RedisSet[ForeignKey[T]]` re-arms every set-member child to its own `Meta.ttl`; likewise a `RedisPriorityQueue[ForeignKey[T]]` re-arms every sorted-set-member child — delivered server-side and atomically at set-time in the same operation as inline-reached children, with no partial application or TOCTOU gap. This holds when invoked through the public API (`asave`, `aset_ttl(cascade=True)`, `refresh_ttl`), not only via a direct Function call.
  2. Traversal through SF containers is cycle-safe (shared visited-set / best-budget-per-node) and honors the per-subtree depth budget: diamonds (both mixed inline+SF and SF-only dual-edge), children reachable both inline and via an SF container, and self-references held in a set/PQ all terminate and are re-armed exactly as the shared budget/visited rules dictate.
  3. Existing behavior is preserved: inline FK cascade shapes (direct, collection-of-FK, nested-submodel), `Meta.ttl`/`refresh_ttl`, and non-cascade models are unchanged — the SF-held-ref reach is additive and opt-in, and the prior TTL/cascade regression suites pass unmodified.
  4. The new reach is proven under the dual test strategy — fakeredis (unit) and real Redis Stack :6370 (integration) — covering the real-Redis-7+ Function traversal path and the fakeredis root-own-`EXPIRE` fallback, honoring the documented fakeredis/real-Redis divergences.
  5. The TTL Cascade documentation (docs site + docstrings) states that SF-held references (`RedisSet` / `RedisPriorityQueue` of `ForeignKey`) participate in cascade, with the coverage matrix updated to include the two new shapes.
**Plans**: 4 plans
  - [x] 02-01-PLAN.md — Implement the SF-container read branch in push_edges (library.lua) + hard-shape fixtures + real-Redis :6370 direct-FCALL integration proof (CASF-04..08)
  - [x] 02-02-PLAN.md — Fakeredis root-own-EXPIRE fallback proof for SF-held-ref cascade (CASF-09)
  - [x] 02-03-PLAN.md — Extend TTL Cascade docs with the coverage matrix + worked example + divergence note (CASF-10)
  - [x] 02-04-PLAN.md — Fix the model-level cascade-trigger gate so asave/aset_ttl/refresh_ttl actually invoke the cascade Function for SF-only cascade-enabled parents, proven via mock-based unit test + real-Redis :6370 public-API integration test (CASF-04..06)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Classify SF-held FK references into the cascade plan | 1/1 | Complete   | 2026-07-24 |
| 2. Traverse SF-held references server-side and re-arm children | 4/4 | Complete   | 2026-07-25 |
