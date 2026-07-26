# Feature Research

**Domain:** Cascade + TTL configuration for a Python Redis ORM (`rapyer`) — first slice of a configurable cascade framework (`CascadeTTL` on `ForeignKey`/`Reference` fields)
**Researched:** 2026-07-06
**Confidence:** HIGH (cascade config APIs verified against SQLAlchemy 2.0, Django, Prisma, redis-om, Beanie docs; Redis `EXPIRE` NX/XX/GT/LT and redis-py signature verified against official docs)

## Feature Landscape

Prior art surveyed: **SQLAlchemy** (`relationship(cascade="...")` string of named operations), **Django** (`ForeignKey(on_delete=...)` with symbolic handlers), **Prisma** (`@relation(onDelete: ...)` referential actions), **redis-om-python** (`Meta.default_ttl`, per-model, no cross-reference propagation), **Beanie ODM** (`Link` + `WriteRules`/`DeleteRules` enums, `fetch_links` depth). The consistent shape across all of them: **cascade behavior is a small set of named, symbolic options declared per relationship, with a sensible default**, never a raw boolean or a free-form callback.

### Table Stakes (Users Expect These)

Features users assume exist because every mature ORM has them. Missing these = the feature feels half-built.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-field opt-out / enable | Django *requires* `on_delete` per FK; SQLAlchemy per `relationship`; Beanie per-call `link_rule`. Users expect to control cascade one relationship at a time — a shared `Author` referenced by many `Book`s must be excludable. | LOW | An `enabled: bool` on `CascadeTTL`; a disabled config makes the FK behave exactly as today (TTL stops at the parent). |
| Global default + per-field override | redis-om's `Meta.default_ttl` sets a model-wide default; SQLAlchemy's `cascade` default (`save-update, merge`) applies unless overridden. This is the milestone's stated config model. | MEDIUM | Global default resolved at `init_rapyer()` / config; per-field annotation wins. Must layer cleanly on the existing `Meta.ttl` / `refresh_ttl` surface without a third competing knob. |
| Cycle-safe traversal / max-depth guard | Prisma explicitly forces `NoAction` to break cascade cycles; every graph-cascade system must terminate. rapyer's FK graphs can contain cycles (self-reference `Tree.parent` is documented). | MEDIUM | Visited-set cycle detection + integer `depth` cap. Non-negotiable given self-references already ship. |
| Named/symbolic config object, not a bare bool | SQLAlchemy strings (`"all, delete-orphan"`), Django symbols (`CASCADE`, `SET_NULL`), Prisma enums. Users expect a readable, discoverable option surface, and the milestone wants an *extensible* backbone. | LOW | A `CascadeTTL` pydantic model with named fields/enums, not `cascade_ttl=True`. Enables self-documenting IDE completion and future delete/save reuse. |
| Backward-compatible with today's `Meta.ttl` / `refresh_ttl` | Existing users rely on root-aggregate TTL. A brownfield milestone must not change behavior for models that never opt in. | LOW | Global default ships **disabled**; TTL crossing an FK is strictly opt-in. Constraint from PROJECT.md. |
| Atomic, set-time propagation | The core value proposition — no partial/interleaved TTL application, no TOCTOU gap. RDBMS cascades are transactional; users expect the same integrity. | HIGH | Single server-side unit (Lua traversal) or one transactional pipeline of `EXPIRE`s. This is where the real engineering is. |

### Differentiators (Competitive Advantage)

Features that set rapyer apart. These align directly with the Core Value: give Redis users the relational-ORM experience existing Redis ORMs lack.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **TTL cascade across references at all** | **No Redis ORM does this.** redis-om only has a flat, per-model `default_ttl`; it never propagates a parent's expiry to referenced children. SQLAlchemy/Django have no TTL concept. This is genuinely novel and is the milestone's headline. | HIGH | The whole point. Everything else is ergonomics around this. |
| Extend-vs-overwrite semantics via native Redis flags | Solves the classic footgun: a short-lived referrer shouldn't shorten a long-lived shared child. Maps *directly* to Redis 7 `EXPIRE ... GT/NX/XX/LT` — precise, atomic, zero extra round trips, no read-then-branch. | MEDIUM | Verified: `EXPIRE key ttl GT` only lengthens; `NX` only sets if unset; a non-volatile key is treated as *infinite* TTL for GT, so `EXTEND` mode never starts expiring a previously-persistent shared child. redis-py `expire(name, time, nx=, xx=, gt=, lt=)` and Lua `redis.call('EXPIRE', k, t, 'GT')` both support it. Strong, defensible default (`EXTEND`). |
| Configurable traversal depth as a first-class knob | Beanie exposes link-fetch depth via `nesting_depth`; users want "cascade one hop" vs "cascade the whole aggregate." Depth turns TTL cascade into a tunable aggregate-lifetime tool. | MEDIUM | `depth` int on `CascadeTTL` (0 = root only, 1 = direct children, N = N hops), always cycle-guarded. |
| Extensible cascade backbone (rule abstraction) | Mirrors Django's `on_delete` symbol design so future `ON DELETE` / `ON SAVE` land as *sibling* cascade rules on the same traversal engine — no redesign. Signals a coherent roadmap, not a one-off. | HIGH | Design the traversal + rule-dispatch now; implement only the TTL rule. The `ActionGroup` flag/`mark_actions` pattern already in the codebase is the natural template for a `CascadeRule` registry. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Expiry-event cascade (re-cascade when a parent key actually expires) | "When the parent dies, cascade to children" feels like the natural trigger. | **Impossible by construction** — once the parent's JSON expires it's gone, so the FK graph is unreachable. Redis keyspace-expiry events are also best-effort/lossy. | Set-time cascade only: resolve and stamp all TTLs when the parent is written, while the graph is still readable. (PROJECT.md Key Decision.) |
| Per-child distinct TTL *values* (a child holding a different absolute TTL than the cascade) | "Give the child its own lifetime." | Ambiguous semantics (whose value wins on multi-parent children?), needs per-edge TTL storage, and blurs the line with a child's own `Meta.ttl`. High complexity for unclear payoff. | Keep cascade as *propagation of the parent's TTL*, modulated only by `mode` (GT/NX). A child that needs an independent lifetime opts out and sets its own `Meta.ttl`. Explicitly TBD/deferred in PROJECT.md. |
| Delete cascade now (`ON DELETE CASCADE/SET NULL/RESTRICT`) | It's the most familiar RDBMS cascade; users will ask for it first. | Real referential integrity needs reverse lookups (who references me) and is a much larger surface. Shipping it half-built erodes trust. | Build the backbone to accept it; implement only TTL this milestone. Out of scope per PROJECT.md. |
| Save cascade (persist children atomically on parent save) | Convenient one-call graph writes. | Multiplies atomicity/ordering complexity and interacts with `get_or_create` SF-save ordering. | Future cascade-framework rule on the same engine. Out of scope. |
| Reverse / inbound cascade (child expiry drives parent, or "expire everyone who references me") | Symmetry with delete-cascade intuition. | rapyer FKs are one-directional inline key strings with **no reverse index**; reverse traversal needs a secondary index and full scans — expensive and TOCTOU-prone. | Forward-only (`parent → referenced child`) cascade in v1. Reverse is a future feature gated on a reference index. |
| Referential-integrity enforcement / existence validation on save | "Cascade implies the reference is valid." | Orthogonal concern; rapyer deliberately does *not* validate FK existence on save (documented). Coupling it to TTL cascade scope-creeps two features into one. | Keep separate. Cascade skips unresolved/missing children gracefully rather than enforcing existence. |
| Cascade as eager-load / `select_related` coupling | "If I traverse for TTL, load the objects too." | Conflates lifetime management with fetch strategy; `afetch` is explicitly lazy and I/O-explicit by design. | Cascade resolves *keys* for `EXPIRE`, not hydrated models. Eager-load stays a separate future feature (docs already flag it). |
| Free-form callback / custom cascade function per field | Maximum flexibility. | Un-atomic (can't run arbitrary Python server-side in one unit), hard to reason about, no prior ORM does this for cascade. | Fixed, named `mode` enum backed by native Redis semantics — atomic and predictable. |

## Recommended `CascadeTTL` Config Schema

Grounded in the prior-art shape (small set of named symbolic options + sensible default) and in Redis 7 `EXPIRE` flag semantics.

```python
class TTLCascadeMode(enum.Enum):
    # maps 1:1 to Redis 7 EXPIRE conditional flags (verified)
    OVERWRITE = "overwrite"  # unconditional EXPIRE — parent lifecycle strictly governs children
    EXTEND    = "extend"     # EXPIRE ... GT — only lengthen a child's TTL, never shorten (DEFAULT)
    IF_UNSET  = "if_unset"   # EXPIRE ... NX — only stamp children that currently have no TTL

class CascadeTTL(BaseModel):
    enabled: bool = True                       # per-field opt-out
    depth: int = 1                             # 0 = root only, 1 = direct children, N = N hops (cycle-guarded)
    mode: TTLCascadeMode = TTLCascadeMode.EXTEND
    # direction is fixed to forward (parent -> referenced child) in v1; not exposed as a knob yet
```

**Knob rationale (prior-art justified):**

- **`enabled` (opt-out)** — Every surveyed ORM allows disabling cascade per relationship (Django per-FK, SQLAlchemy per-`relationship`, Beanie per-call rule). Required for shared children. LOW cost.
- **`depth` (cycle-safe traversal)** — Beanie exposes fetch depth; Prisma forces cycle-breaking. Default `1` is conservative and backward-compat-friendly (only direct children get stamped unless the user asks for deeper aggregate lifetime). Always paired with a visited-set guard so cycles terminate regardless of `depth`.
- **`mode` (extend-vs-overwrite)** — The strongest, most defensible recommendation. `EXTEND` (Redis `GT`) is the **default** because: (a) it matches rapyer's existing *refresh*-TTL philosophy (push expiry out, don't cut life short); (b) `GT` treats a non-volatile key as infinite TTL, so `EXTEND` will **never** begin expiring a child that was intentionally persistent — killing the classic "a shared parent got expired because one short-lived referrer touched it" footgun; (c) it's a single atomic server-side flag, no read-then-branch. `OVERWRITE` (plain `EXPIRE`) is offered for strict parent-governs-child lifecycles. `IF_UNSET` (`NX`) covers "only give children a default lifetime." `LT`/`SHORTEN` deliberately omitted from v1 (rarely wanted; add later without breaking the enum).
- **`direction` fixed forward** — rapyer FKs have no reverse index; reverse cascade is an anti-feature for now (see above). Kept out of the schema so adding it later is additive, not a semantics change.

### Global-default + per-field-override ergonomics

Follow the existing codebase DSL. rapyer already uses `Annotated`-metadata markers (`Key[...]`, `Index[...]`, `SafeLoad[...]` in `rapyer/fields/`) and per-model `Meta` config. Recommend the same two-layer shape:

- **Global default** — a single `CascadeTTL` set at `init_rapyer(..., cascade_ttl=CascadeTTL(...))` (assigned onto models the same way `Meta.ttl` is wired in `init.py`), or a module-level `DEFAULT_CASCADE_TTL`. Ships as `CascadeTTL(enabled=False)` so existing projects are unchanged until they opt in (backward-compat constraint).
- **Per-field override** — an `Annotated` marker on the reference field, consistent with `Index[...]`:
  ```python
  class Book(AtomicRedisModel):
      author: Annotated[Reference[Author], CascadeTTL(mode=TTLCascadeMode.OVERWRITE, depth=2)]
      cache_hint: Reference[Blob]  # inherits the global default
  ```
  This reuses rapyer's established annotation-collection machinery rather than inventing a new declaration site, and per-field beats global — mirroring SQLAlchemy/Django/Prisma per-relationship precedence.

## Feature Dependencies

```
CascadeTTL config object (named schema)
    └──requires──> Cascade backbone (rule abstraction + traversal engine)
                       └──requires──> Cycle-safe depth traversal (visited-set + depth cap)
                                          └──requires──> FK key resolution across the graph

Atomic set-time propagation
    └──requires──> Cascade backbone
    └──requires──> Redis 7 EXPIRE GT/NX/XX flags (for `mode`)   [server: Lua or pipelined redis-py]

Global default + per-field override
    └──requires──> CascadeTTL config object
    └──enhances──> existing Meta.ttl / refresh_ttl surface (must coexist)

Delete cascade (future) ──reuses──> Cascade backbone
Save cascade   (future) ──reuses──> Cascade backbone
Reverse-direction cascade (future) ──requires──> a reference/reverse index (does not exist)
```

### Dependency Notes

- **`mode` requires Redis 7 EXPIRE flags:** `GT`/`NX`/`XX`/`LT` are Redis 7.0+; Redis Stack (RedisJSON + RediSearch) is built on Redis 7+, so this is satisfied — but flag it as an explicit minimum-version constraint, and confirm the fakeredis unit path supports the conditional flags (a known fakeredis/real-Redis divergence risk per CONCERNS.md; if unsupported, unit tests must exercise `mode` against real Redis Stack).
- **Config object requires the backbone:** The schema is only meaningful once a traversal engine consumes it. Build them in the same phase; ship the TTL rule as the backbone's first (and only) implemented rule.
- **Atomicity choice (Lua traversal vs Python-side key resolution + pipelined EXPIRE):** Deferred to architecture research per PROJECT.md. Both can use the GT/NX flags. Python-side resolution is simpler but multi-round-trip/TOCTOU-prone; a single Lua traversal is one true atomic unit. This is the highest-complexity decision and the main phase-ordering risk.

## MVP Definition

### Launch With (v1)

- [ ] `CascadeTTL` named config object (`enabled`, `depth`, `mode`) — the discoverable, extensible surface
- [ ] `mode` with at least `OVERWRITE` + `EXTEND` (GT) — the differentiating semantics; `EXTEND` default
- [ ] Cycle-safe depth traversal — required for correctness given self-references
- [ ] Global default (ships disabled) + per-field `Annotated` override — the stated config model, backward compatible
- [ ] Atomic set-time propagation across enabled forward references — the Core Value
- [ ] Coexistence with existing `Meta.ttl` / `refresh_ttl` — brownfield constraint

### Add After Validation (v1.x)

- [ ] `IF_UNSET` (NX) and optionally `LT`/`SHORTEN` modes — once base semantics are proven and requested
- [ ] Delete cascade on the same backbone — the most-requested next cascade rule
- [ ] Eager-load / depth-controlled fetch (`select_related`-style) — already flagged in FK docs as follow-up

### Future Consideration (v2+)

- [ ] Reverse-direction cascade — gated on building a reference/reverse index
- [ ] Per-child distinct TTL values — only if a concrete use case emerges; semantics must be resolved first
- [ ] Referential-integrity enforcement — separate feature track from cascade

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `CascadeTTL` named config object | HIGH | LOW | P1 |
| Atomic set-time propagation | HIGH | HIGH | P1 |
| Cycle-safe depth traversal | HIGH | MEDIUM | P1 |
| `mode` OVERWRITE + EXTEND (GT) | HIGH | MEDIUM | P1 |
| Global default + per-field override | HIGH | MEDIUM | P1 |
| Backward-compat with `Meta.ttl` | HIGH | LOW | P1 |
| Extensible cascade backbone | MEDIUM | HIGH | P1 (design), P2 (extra rules) |
| `IF_UNSET` / `LT` modes | LOW | LOW | P2 |
| Delete cascade | HIGH | HIGH | P2 |
| Reverse-direction cascade | MEDIUM | HIGH | P3 |
| Per-child TTL values | LOW | HIGH | P3 |

**Priority key:** P1 = must have for launch · P2 = should have, add when possible · P3 = defer until PMF.

## Competitor Feature Analysis

| Feature | SQLAlchemy | Django | redis-om-python | Beanie ODM | rapyer approach |
|---------|-----------|--------|-----------------|------------|-----------------|
| Cascade declaration site | `relationship(cascade="save-update, delete, delete-orphan")` string | `ForeignKey(on_delete=CASCADE)` symbolic, **required** | none (only flat `Meta.default_ttl`) | per-call `link_rule=DeleteRules.DELETE_LINKS` enum | `CascadeTTL(...)` named object; global default + `Annotated` per-field override |
| Cascade options | save-update, merge, expunge, delete, delete-orphan, refresh-expire | CASCADE, PROTECT, RESTRICT, SET_NULL, SET_DEFAULT, DO_NOTHING | — | DO_NOTHING, DELETE_LINKS / WRITE | `TTLCascadeMode`: OVERWRITE, EXTEND, IF_UNSET |
| Default behavior | `save-update, merge` | none — must be explicit | no TTL unless `default_ttl` set | DO_NOTHING | global default disabled; `EXTEND` when enabled |
| TTL propagation across relationships | n/a | n/a | **no** (per-model only) | **no** | **yes — the differentiator** |
| Cycle handling | app responsibility | DB responsibility | n/a | app responsibility | explicit visited-set + `depth` cap |
| Depth control | n/a | n/a | n/a | `fetch_links` / nesting depth (for loads) | `depth` on `CascadeTTL` (for TTL propagation) |
| Extend-vs-overwrite TTL | n/a | n/a | overwrite on save | n/a | native Redis `GT`/`NX`/`XX` flags |

## Sources

- [Cascades — SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/orm/cascades.html) — cascade option set (save-update, merge, expunge, delete, delete-orphan, refresh-expire), `all` synonym, defaults
- [Foreign Keys on_delete Option in Django Models — GeeksforGeeks](https://www.geeksforgeeks.org/python/foreign-keys-on_delete-option-in-django-models/) and [Django on_delete — Sentry](https://sentry.io/answers/django-on-delete/) — CASCADE/PROTECT/RESTRICT/SET_NULL/SET_DEFAULT/DO_NOTHING semantics
- [Referential actions — Prisma Documentation](https://www.prisma.io/docs/orm/prisma-schema/data-model/relations/referential-actions) — referential action set, defaults, cascade cycle handling (NoAction to break cycles)
- [redis-om-python models docs](https://github.com/redis/redis-om-python/blob/main/docs/models.md) and [Feature Request: default expiry (#529)](https://github.com/redis/redis-om-python/issues/529) — `Meta.default_ttl` per-model, applied on save/add; no cross-reference propagation
- [Relations — Beanie Documentation](https://beanie-odm.dev/tutorial/relations/) and [Announcing Beanie ODM 1.8](https://dev.to/romanright/announcing-beanie-odm-18-relations-cache-actions-and-more-24ef) — `Link`, `WriteRules` (DO_NOTHING/WRITE), `DeleteRules` (DO_NOTHING/DELETE_LINKS), `fetch_links` depth
- [EXPIRE — Redis Docs](https://redis.io/docs/latest/commands/expire/) — NX/XX/GT/LT conditional flags (Redis 7.0+), non-volatile-key-as-infinite semantics for GT/LT
- [Redis Commands — redis-py docs](https://redis.readthedocs.io/en/stable/commands.html) — verified `expire(name, time, nx=False, xx=False, gt=False, lt=False)` async signature
- rapyer codebase: `.planning/PROJECT.md`, `.planning/codebase/ARCHITECTURE.md` (Foreign Keys and Cascade Behavior section), `rapyer/types/foreign_key.py`, `rapyer/types/relational.py`, `rapyer/config.py`, `docs/documentation/special-fields/foreign-keys.md`

---
*Feature research for: cascade + TTL configuration in a Python Redis ORM*
*Researched: 2026-07-06*
