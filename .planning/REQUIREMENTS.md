# Requirements — Milestone v1.3.6: Cascade Reach Through Special-Field References

> Ships in release v1.3.6 alongside RedisText (a separate, isolated milestone). Builds directly on v1.3.5 Configurable TTL Cascade. Scope: **traversal-reach only** — extend the shared cascade walker to reach `ForeignKey` references held inside special-field containers (`RedisSet`, `RedisPriorityQueue`). The apply layer (per-child cascading-TTL-refresh) is reused unchanged; no new save/update/delete cascade action is introduced.

## v1.3.6 Requirements

### Cascade traversal into special-field references (CASF)

- [x] **CASF-01**: A user can declare a special field whose elements are references to another model — `RedisSet[ForeignKey[T]]` and `RedisPriorityQueue[ForeignKey[T]]` — with the refs stored as the target's key strings under the special field's own Redis key (SET / ZSET), never inline in the parent JSON document.
- [x] **CASF-02**: A user can enable cascade on such an SF-held-ref field via a per-field `CascadeTTL` annotation or the global `init_rapyer(cascade_ttl=...)` default, with the same precedence as inline FK fields (field > global > off).
- [x] **CASF-03**: `build_cascade_plan` classifies SF-held-ref fields into the static per-class plan table as their own edge shape — recording the special-field key suffix, the target class, and the depth budget — distinct from the existing inline FK edge shapes and from the existing SF-key-refresh suffixes.
- [ ] **CASF-04**: When a cascade fires on a parent (`asave`, `aset_ttl(cascade=True)`, `refresh_ttl`), the server-side Redis Function traversal reads each cascade-enabled `RedisSet` key (its members) and follows every `ForeignKey` reference found there.
- [ ] **CASF-05**: Likewise for `RedisPriorityQueue`: the server-side traversal reads the sorted-set members and follows every `ForeignKey` reference found there.
- [ ] **CASF-06**: Each child reached via an SF-held reference is re-armed to its own `Meta.ttl` (the per-child *cascading refresh*), applied atomically and server-side at set-time in the same operation as inline-reached children — no partial application, no TOCTOU gap.
- [ ] **CASF-07**: Traversal through SF containers is cycle-safe (shared visited-set / best-budget-per-node) and honors the per-subtree depth budget, including diamonds and shared children reachable both inline and via an SF container, and self-references held in a set/PQ.
- [ ] **CASF-08**: Existing behavior is preserved byte-for-byte — inline FK cascade shapes (direct, collection-of-FK, nested-submodel), `Meta.ttl`/`refresh_ttl`, and non-cascade models are unchanged; the new SF-held-ref reach is additive and opt-in.
- [ ] **CASF-09**: SF-held-ref cascade is proven under the dual test strategy — fakeredis (unit) and real Redis Stack (integration) — covering the real-Redis-7+ Function traversal path and the fakeredis root-own-`EXPIRE` fallback, and honoring the documented fakeredis/real-Redis divergences (CONCERNS.md).
- [ ] **CASF-10**: The `CascadeTTL` cascade documentation (docs site + docstrings) is extended to state that SF-held references (`RedisSet` / `RedisPriorityQueue` of `ForeignKey`) participate in cascade, with the coverage matrix updated to include the two new shapes.

## Future Requirements (deferred)

- **Save/update-cascade apply through SF-held refs** — re-persisting reached children on parent save/update (the `CascadeSave`/`CascadeUpdate` seam). Explicitly out of this milestone per scope decision (traversal-reach only).
- **Delete-cascade through SF-held refs** — following SF-held references on delete (`CascadeDelete` seam).
- **SF containers holding nested inline submodels** that themselves contain FKs (as opposed to direct `ForeignKey[T]` elements) — reach into deeper SF-element shapes if a real need appears.

## Out of Scope (with reasoning)

- **Any new cascade apply action** (save/update/delete) — the user scoped this milestone to traversal reach only; the apply layer reuses v1.3.5's cascading-TTL-refresh untouched.
- **Per-field TTL *values*** distinct from each child's own `Meta.ttl` — unchanged from v1.3.5; still the per-child own-TTL cascading refresh.
- **Expiry-event cascade** — impossible by construction (an expired parent's data is gone); cascade remains set-time only.
- **New special-field *types*** — this milestone works with the existing `RedisSet` / `RedisPriorityQueue`; RedisText and other SF types are out of scope here.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CASF-01 | Phase 1 | Complete |
| CASF-02 | Phase 1 | Complete |
| CASF-03 | Phase 1 | Complete |
| CASF-04 | Phase 2 | Pending |
| CASF-05 | Phase 2 | Pending |
| CASF-06 | Phase 2 | Pending |
| CASF-07 | Phase 2 | Pending |
| CASF-08 | Phase 2 | Pending |
| CASF-09 | Phase 2 | Pending |
| CASF-10 | Phase 2 | Pending |

**Coverage:** 10/10 v1.3.6 requirements mapped. No orphans, no duplicates.
