# Phase 1: Classify SF-held FK references into the cascade plan - Context

**Gathered:** 2026-07-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Teach `build_cascade_plan` (`rapyer/cascade/planner.py`) to recognize `ForeignKey` references held inside special-field containers — `RedisSet[ForeignKey[T]]` and `RedisPriorityQueue[ForeignKey[T]]` — and emit them into the static per-class cascade plan table as a **distinct SF-held-ref edge shape** (SF key suffix + target class + container kind + depth). Pure annotation introspection; **zero Redis I/O** in this phase.

Covers CASF-01, CASF-02, CASF-03. The server-side traversal that consumes these edges (reading SET/ZSET members and following the refs) is **Phase 2** — not this phase.

**Verified starting fact:** `RedisSet[ForeignKey[T]]` / `RedisPriorityQueue[ForeignKey[T]]` fields land only in `_special_field_names`, **never** in `_contain_fk` — `contains_fk_field()` returns `False` for SF types (only `GenericRedisType`, i.e. `RedisList`/`RedisDict`, overrides it to recurse). So today such a field emits a refresh-only special-suffix (its own key gets `EXPIRE`d) but **no cascade edge at all** — the FK strings inside the set/zset are never followed. This phase closes that gap on the planner side.

</domain>

<decisions>
## Implementation Decisions

### Edge representation (D-01)
- **D-01:** Represent the SF-held-ref edge as a `CascadeEdge` kept in the **same `entry.fks` list**, adding a discriminator + key locator to the dataclass (e.g. `sf_container: "set" | "zset" | None` and the SF **key suffix**). Rejected: a separate `sf_fk_edges` list (forces a validator extension + duplicate traversal wiring) and overloading `special_suffixes` into objects (breaks the load-bearing "suffixes are EXPIRE'd, never followed" invariant the milestone forbids changing).
- **D-01a:** `sf_container` MUST default to `None` and be dropped by `cascade_plan_json`/`_drop_none_values`, so existing direct/collection edges serialize byte-identically and the plan hash is **unchanged for non-SF models** (additive/opt-in constraint).
- **D-01b:** For an SF edge, the locator is the SF **key suffix** (dotted path used to build `__rapyer_special__:{model_key}:{suffix}`), NOT an inline `$.field` JSONPath — because SF members live under a separate key. The Phase-2 Lua branches on `sf_container` to read via `SMEMBERS`/`ZRANGE` instead of joining the single `JSON.GET` batch in `push_edges`.

### Discovery / classification path (D-02)
- **D-02:** Discover SF-held-ref fields via a **dedicated pass inside `rapyer/cascade/planner.py`** over `_special_field_names`, keeping a field when `_unwrap_relational_target(annotation)` is non-`None`. **Do NOT edit** the `__init_subclass__` field-classification loop in `base.py` (CLAUDE.md flags it as fragile; v1.3.5 deliberately left it untouched). Rejected: a new `_sf_fk_field_names` classification set in `base.py` (edits the fragile loop, process-wide blast radius, no Phase-1 benefit) and redirecting the `_contain_fk` branch (non-viable — the field isn't in `_contain_fk`).
- **D-02a:** Target-class resolution needs **no new logic** — `_unwrap_relational_target` already strips `Optional` and recurses generic args (`RedisSet → ForeignKey[Author] → Author`).
- **D-02b:** The new SF edge and the existing refresh-only special-suffix are **complementary, not redundant** — they act on different Redis keys (the suffix `EXPIRE`s the SF container key; the edge follows its members to targets). Both should be emitted for the same field. Guard against future double-emission if nested-SF interplay is added later.

### Depth & collection semantics (D-03)
- **D-03:** Mirror the existing collection-of-FK edge exactly: **`is_collection=True`** — one edge per SF field covers every member, all sharing one depth budget; entering the SF field costs one hop, so `CascadeTTL(depth=N)` counts hops identically to inline `list[ForeignKey[T]]`. `resets_depth_budget` follows the same per-field-override-vs-global rule via `_classify_edge`. Rejected: a two-level (container-hop + member-hop) budget (contradicts the inline-collection mental model) and runtime SF-source inference in Lua (pushes SF-type lookup into the hot path).
- **D-03a:** Cycle-safety reused unchanged — `push_child` / the best-budget-per-node `visited` map key purely on the resolved target-key string, so a child reachable both inline and via an SF container dedups through the same map, and a self-reference held in a set/PQ terminates via the same backstop. No new cycle reasoning.

### Fail-fast validation (D-04)
- **D-04:** Because SF-held-ref edges live in `entry.fks` (D-01), `validate_cascade_ttl_targets` covers their targets **for free** — no validator change. Reuse `CascadeTargetTtlMissingError` as-is. Only work: a regression test proving a cascade-enabled SF-held-ref target with `Meta.ttl=None` fails fast at `init_rapyer()`, and that the root-with-only-SF-edges case is also caught (roots are flagged via `entry.fks` being non-empty).
- **D-04a:** A distinct "reached via RedisSet/PriorityQueue field" error message/subtype is **deferred** — `edge.path`/suffix already localizes the offending field; revisit only if real usage shows the generic message is confusing.

### Claude's Discretion
- Exact `CascadeEdge` field names (`sf_container` vs `special_kind`, etc.) and whether the SF key suffix reuses the `special_suffixes` string form — planner/implementer's call, provided D-01/D-01a/D-01b hold.
- Precise shape of the Phase-1 unit assertions (plan-dict vs plan-JSON), as long as they prove the new edge shape, `None`-drop for non-SF models, precedence (field > global > off), and the fail-fast case.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### This milestone's planning
- `.planning/PROJECT.md` §"Current Milestone: v1.3.6 Cascade Reach Through Special-Field References" — goal, scope (traversal-reach only), constraints
- `.planning/REQUIREMENTS.md` — CASF-01..10; Phase 1 owns CASF-01/02/03
- `.planning/ROADMAP.md` — Phase 1/2 split and success criteria

### v1.3.5 cascade backbone (the code being extended)
- `rapyer/cascade/planner.py` — `CascadeEdge` (~42), `CascadePlanEntry` (~71), `_classify_edge` (~96), `_resolve_target_cls`/`_unwrap_relational_target` (~28/110), `_static_walk_fk_edges` (~126), `_static_walk_special_suffixes` (~189), `build_cascade_plan` (~219), `validate_cascade_ttl_targets` (~241), `cascade_plan_json`/`_drop_none_values` (~282/295)
- `rapyer/cascade/spec.py`, `rapyer/cascade/ttl.py` — `CascadeTTL`/`CascadeSpec` config surface + precedence
- `rapyer/scripts/lua/cascade/library.lua` — the Redis Function; `push_edges` (~233) single-`JSON.GET` batch (~242), `is_collection` branch (~258/264), `special_suffixes` EXPIRE (~199) — **consumed in Phase 2, not this phase, but constrains the edge shape**
- `rapyer/base.py` — `__init_subclass__` field classification (~404-446, DO NOT EDIT), `contains_fk_field` (~721), `_special_field_names`/`_contain_fk`/`_contain_sf`/`_relational_field_names`
- `rapyer/errors/cascade.py` — `CascadeTargetTtlMissingError`
- `rapyer/init.py` — `build_cascade_plan` + `validate_cascade_ttl_targets` call site (~84)
- `rapyer/types/redis_set.py`, `rapyer/types/priority_queue.py`, `rapyer/types/special.py`, `rapyer/types/base.py` (`contains_fk_field` ~59), `rapyer/types/generic.py` (override ~48), `rapyer/types/foreign_key.py`, `rapyer/types/relational.py`

### Cascade design history (semantics to preserve)
- `.planning/PROJECT.md` §"Foreign Keys and Cascade Behavior" / §"Key Decisions" — per-child own-TTL cascading refresh, set-time-only, server-side traversal (D-01/D-04/D-06 from v1.3.5)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_unwrap_relational_target` (`planner.py:28`) — already resolves the FK target class through `Optional[...]` and nested generic containers; reuse verbatim for SF-held refs.
- `_classify_edge` (`planner.py:96`) — per-field `CascadeTTL` spec > global blanket precedence; reuse to set `enabled`/`depth`/`resets_depth_budget` on the SF edge.
- `cascade_plan_json` + `_drop_none_values` (`planner.py:282/295`) — a `None` discriminator field serializes away, keeping non-SF plan bytes/hash stable.
- `validate_cascade_ttl_targets` (`planner.py:241`) — edge-representation-agnostic; covers SF targets automatically once edges are in `entry.fks`.

### Established Patterns
- v1.3.5 added all cascade classification inside `rapyer/cascade/` **without touching** `base.py.__init_subclass__` — follow that precedent (D-02).
- Static plan-table = pure introspection, no Redis; every model gets exactly one `CascadePlanEntry`. Phase-1 tests assert on the returned plan dict/JSON.
- `special_suffixes` are refresh-only (EXPIRE), never followed — a hard invariant; the SF edge is a separate mechanism (D-02b).

### Integration Points
- `build_cascade_plan(REDIS_MODELS)` called in `rapyer/init.py:84`, immediately followed by `validate_cascade_ttl_targets` — the new edge flows through both with no call-site change.
- The `CascadeEdge` shape is the contract the Phase-2 `library.lua` will branch on (`sf_container` → SMEMBERS/ZRANGE read path).

</code_context>

<specifics>
## Specific Ideas

- Both `RedisSet` and `RedisPriorityQueue` are in scope for this milestone (roadmap); the plan must distinguish SET vs ZSET (`sf_container`) so Phase 2 picks the right read command (`SMEMBERS` vs `ZRANGE`).
- Keep the change surface for Phase 1 confined to `rapyer/cascade/planner.py` + the `CascadeEdge` dataclass; no `base.py`, no Lua, no Redis.

</specifics>

<deferred>
## Deferred Ideas

- **Phase 2:** server-side traversal — `library.lua` reads SET/ZSET members via `SMEMBERS`/`ZRANGE`, follows the refs, re-arms each child to its own `Meta.ttl`; dual-backend proof + docs (CASF-04..10).
- **Distinct SF-hop error message/subtype** for fail-fast (D-04a) — deferred unless the generic message proves confusing.
- **SF containers holding nested inline submodels** (vs direct `ForeignKey[T]` elements) — out of milestone scope (REQUIREMENTS "Future").
- **Save/update/delete cascade apply through SF-held refs** — explicitly out of this milestone (traversal-reach only).

</deferred>

---

*Phase: 1-classify-sf-held-fk-references-into-the-cascade-plan*
*Context gathered: 2026-07-24*
