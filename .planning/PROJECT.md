# rapyer — Configurable TTL Cascade

## What This Is

`rapyer` is a Python ORM for Redis that makes Redis feel like a real database — typed models, foreign keys, indexing, and atomic operations — so users write readable, high-level code instead of hand-rolling Redis commands and reasoning about keyspaces themselves. This milestone adds the **first slice of a configurable cascade framework: TTL cascade across `ForeignKey` relationships**, laying the backbone that later delete-cascade and save-cascade work will plug into.

## Core Value

Give Redis users a genuine relational-ORM experience — the cascade/TTL/referential-integrity behaviors people expect from an RDBMS — that existing Redis ORMs lack. If everything else fails, setting a parent's TTL must **atomically and server-side** re-arm every cascade-enabled referenced child at set-time — a *cascading refresh*: each reached child is reset to **its own `Meta.ttl`**, via a single Lua script that both traverses the FK graph and expires the keys in one server-side operation.

> **Decision history:** the mechanism was reframed by the Phase-2 discussion (2026-07-07) from *"propagate the parent's TTL value"* to the per-child *cascading refresh* above, and traversal moved from the Phase-1 Python `CascadePlanner` into the Lua script. See `.planning/phases/02-atomic-ttl-apply-spike-then-implement/02-CONTEXT.md` (D-01, D-04, D-06).

## Current Milestone: v1.3.6 Cascade Reach Through Special-Field References

> Ships in release v1.3.6 alongside RedisText and other v1.3.6 features. Tracked as an isolated GSD milestone on branch `gsd/cascade-update-sf`; builds directly on v1.3.5 Configurable TTL Cascade.

**Goal:** Extend the shared cascade traversal so it discovers `ForeignKey` references held *inside* special-field containers (`RedisSet`, `RedisPriorityQueue`) — a shape v1.3.5's FK-shape traversal never reached — so the existing TTL cascade automatically re-arms those children too. Traversal-reach only; no new apply action.

**Target features:**
- New traversable FK shapes: `RedisSet[ForeignKey[T]]` and `RedisPriorityQueue[ForeignKey[T]]`, where the refs live under the special field's own Redis key (not inline in the parent JSON doc).
- Extend the walker end-to-end: `_cascade_ttl_fields` classification, `CascadePlanner.atraverse`, the static `build_cascade_plan` plan-table, and the server-side traversal (Redis Function / Lua) so it reads SF keys and follows the refs found there.
- Preserve every v1.3.5 guarantee: atomic + server-side at set-time, cycle-safe (visited-set), per-subtree depth budget, per-child own-`Meta.ttl` refresh (the *cascading refresh*).
- Additive and opt-in: no change to existing inline FK shapes, non-cascade models, or `Meta.ttl`/`refresh_ttl` behavior.

**Key context:** The apply layer is unchanged — this reuses today's cascading-TTL-refresh; the whole milestone is a *traversal-reach* extension. Real-Redis-7+ Function path for traversal; fakeredis root-own-`EXPIRE` fallback and the documented fakeredis/real-Redis divergences handled per the existing dual-test strategy. RedisText (the other v1.3.6 feature) is a separate in-flight milestone, isolated — untouched here.

## Requirements

### Validated

<!-- Inferred from existing codebase (see .planning/codebase/). These already ship and are relied upon. -->

- ✓ Typed `AtomicRedisModel` models persisted as RedisJSON documents — existing
- ✓ `ForeignKey` fields storing the target's key string inline, resolved lazily via `afetch`/`aget` — existing
- ✓ Atomic operations via transactional pipelines (MULTI/EXEC) and Lua scripts (`EVALSHA`) with SHA registration + `NoScriptError` self-healing — existing
- ✓ Special-field types (RedisSet, RedisPriorityQueue, etc.) with server-side save/load Lua dispatch — existing
- ✓ RediSearch indexing of model fields — existing
- ✓ Uniform TTL on the root aggregate: `Meta.ttl` + `refresh_ttl` action-group config; `_ttl_keys()` = main key + own (direct/nested) special-field keys — existing (single global int, no per-relationship config)
- ✓ `CascadeTTL` config object on a `ForeignKey` field describing how TTL cascades along that relationship — v1.3.5
- ✓ Config model: global default (`init_rapyer(cascade_ttl=...)`, ships disabled) + per-field `CascadeTTL` override (precedence field > global > off) — v1.3.5
- ✓ Configurable, cycle-safe traversal depth (per-subtree budget, visited-set termination) — v1.3.5
- ✓ TTL propagation to the root's keys **plus** all cascade-enabled children's keysets, applied atomically server-side at set-time — v1.3.5
- ✓ Extensible cascade backbone (traversal-shared / apply-swapped; `CascadeDelete`/`CascadeSave` stubs) — v1.3.5
- ✓ Backward-compatible coexistence with existing `init_rapyer(ttl=...)` / `refresh_ttl` (opt-in, disabled-by-default) — v1.3.5

### Active

<!-- Milestone v1.3.6 (Cascade Reach Through Special-Field References). Formal REQ-IDs defined in REQUIREMENTS.md. -->

- Cascade traversal reaches `ForeignKey` refs held inside `RedisSet[ForeignKey[T]]`
- Cascade traversal reaches `ForeignKey` refs held inside `RedisPriorityQueue[ForeignKey[T]]`
- SF-held-ref shapes classified into the existing `_cascade_ttl_fields` detection + `build_cascade_plan` plan-table
- Server-side traversal (Redis Function / Lua) reads SF keys and follows the refs found there, atomically at set-time
- Existing cascade guarantees preserved for the new shapes: cycle-safety (visited-set), per-subtree depth budget, per-child own-`Meta.ttl` refresh

### Out of Scope

<!-- Explicit boundaries with reasoning, to prevent scope creep. -->

- Delete cascade (ON DELETE CASCADE/SET NULL/RESTRICT) — future cascade-framework work; backbone designed for it but not implemented this milestone
- Save cascade (persisting related children atomically on parent save) — future cascade-framework work
- Expiry-event cascade (reacting to a parent key actually expiring) — **impossible by construction**: once a parent expires its JSON is gone, so children can't be traversed. Cascade is resolved at set-time only.
- Table-like registry + bulk ops (list-all / count / truncate / query-all-of-type) — desired later ("make it feel like any other DB"), not this milestone
- Per-field TTL *values* (a child holding a different TTL than the cascade) — TBD in research; not committed as a requirement yet

## Context

- **Brownfield.** Mature codebase mapped in `.planning/codebase/` (STACK, ARCHITECTURE, STRUCTURE, CONVENTIONS, TESTING, INTEGRATIONS, CONCERNS). Python 3.10–3.13, pydantic v2, redis-py async, Redis Stack (RedisJSON + RediSearch). `uv` + `tox`, extensive CI (lint/mypy/test matrix, coverage, security scans, CodSpeed benchmarks, MkDocs docs).
- **Atomicity mechanics** (verified in code):
  - *Transactional pipelines* (`context.py`): a contextvar-held pipeline; `ensure_pipeline` joins the outer transaction or opens a new `pipeline(transaction=True)`. Bundles a logical action + its TTL refresh into one MULTI/EXEC. **Limit:** cannot read-then-branch mid-transaction.
  - *Lua scripts* (`scripts/`): templates → placeholder/variant substitution → SF-dispatch injection → `SCRIPT LOAD` at `init_rapyer()` → cached SHA → `EVALSHA` (`arun_sha`, self-healing on `NoScriptError`). One atomic server-side unit that **can** read-then-branch (e.g. `get_or_create.lua`). `run_sha` can enqueue `evalsha` inside a pipeline.
- **TTL today never crosses a ForeignKey** — it covers only the root aggregate's own keys. Cascade is a genuinely new traversal.
- Motivation from the user: today rapyer users repeat Redis actions, must understand Redis deeply, and the resulting code isn't readable — the standard reasons to reach for an ORM, which existing Redis ORMs serve poorly. Cascade config is also noted as explicitly deferred in CHANGELOG 1.3.2; this milestone starts defining it.

## Constraints

- **Atomicity**: The entire TTL-cascade propagation must be a single atomic operation applied server-side at set-time. No partial/interleaved application; no TOCTOU gap.
- **Tech stack**: Must fit existing architecture — pydantic v2 models, transactional-pipeline + Lua-script/`EVALSHA` machinery, SF-dispatch injection pattern, `init_rapyer()` registration lifecycle.
- **Compatibility**: Must not break existing `Meta.ttl` / `refresh_ttl` behavior or existing `ForeignKey` usage; changes should be additive/opt-in.
- **Cycle safety**: FK graphs may contain cycles; traversal must detect cycles and honor a max-depth guard.
- **Testing**: Must hold under the existing dual test strategy — fakeredis (unit) and real Redis Stack (integration) — including the known fakeredis/real-Redis divergences noted in CONCERNS.md.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Cascade trigger = set-time only (no expiry-event cascade) | An expired parent's JSON is gone; children become unreachable, so expiry-event cascade is impossible | ✓ Good |
| Config surface = global default + per-field `CascadeTTL` override | User choice; mirrors familiar ORM defaulting while keeping per-relation control | ✓ Good — shipped v1.3.5 |
| Build extensible cascade backbone, implement only TTL now | "Start defining cascade, specifically TTL"; avoids rework when delete/save cascade land | ✓ Good — shipped v1.3.5 (`CascadeDelete`/`CascadeSave` stubs demonstrate the seam) |
| Apply mechanism: EVALSHA Lua script **vs** Redis Functions library | EVALSHA re-executes the whole body each call; a `FUNCTION LOAD` library captures the decoded plan once as an upvalue → ~0 per-call cost | ✓ **Resolved post-milestone (quick task, 2026-07-16): Redis Functions library** (`FCALL`). Cascade traversal is now real-Redis-7+-only; fakeredis falls back to a root-own `EXPIRE` loop. 11–46% faster than the last EVALSHA baseline. |
| Missing-cascade-function self-heal at set-time | A reload-and-retry on a missing Function was prototyped but broadened core pipeline execution beyond a cleanup's scope | ⚠ Revisit — **deferred to issue #284**; production currently propagates the FCALL error if the Function is missing |
| Traversal resolution: server-side Lua traversal **vs** Python-side key resolution feeding a simpler script | Both are viable; server-side Lua is one true atomic op, Python-side is simpler but multi-round-trip/TOCTOU-prone | ✓ **Resolved (Phase-2 discussion, 2026-07-07): server-side Lua** — traversal + expiry in one script, retiring the TOCTOU. Supersedes STATE.md's earlier "Option B" accumulated decision. See 02-CONTEXT.md D-01/D-02/D-03. |
| TTL semantics: propagate parent's TTL **vs** re-arm each child to its own TTL | Per-child own-TTL is order-independent for shared children and needs no `GT`/`NX` flags (relative `EXPIRE`, works on all Redis 6.0–7.4); parent-propagation guarantees children outlive the parent but reopens the version-flag question | ✓ **Resolved (Phase-2 discussion, 2026-07-07): per-child own TTL** — a cascading refresh; validate on ship. See 02-CONTEXT.md D-04/D-05. |
| Cascade-reachable target must declare `Meta.ttl` | Fail-fast beats a silent runtime no-op | ✓ **Resolved (Phase-2 discussion, 2026-07-07): raise at `init_rapyer()`** after FK-target resolution. See 02-CONTEXT.md D-08. |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*2026-07-24 — **Milestone v1.3.6 (Cascade Reach Through Special-Field References) started** via `/gsd:new-milestone` in an isolated `.planning/` on branch `gsd/cascade-update-sf`. Extends the v1.3.5 shared cascade traversal to reach `ForeignKey` refs held inside `RedisSet` / `RedisPriorityQueue` special-field containers (a shape the v1.3.5 FK-shape traversal never covered), so the existing TTL cascade re-arms those children too. Traversal-reach only — apply layer (cascading-TTL-refresh) unchanged. Ships in release v1.3.6 alongside RedisText (a separate, isolated milestone). Phases start fresh at Phase 1. — Prior milestone note follows.*

*2026-07-20 — **Milestone v1.3.6 (RedisText — Text + Embeddings + Semantic Search) started** via `/gsd:new-milestone`. New special field type storing text + a vector embedding, KNN-searchable via a RediSearch VECTOR index over the SF-key prefix; embeddings via redisvl (optional `rapyer[embeddings]` extra); save rides the transactional pipeline like other SF fields. Feasibility de-risked by three VALIDATED spikes (`.planning/spikes/`); design locked in `.planning/notes/redistext-design-decisions.md`. Phases continue from Phase 5. — Prior milestone-close note follows.*

*Last updated: 2026-07-20 — **Milestone v1.3.5 (Configurable TTL Cascade) shipped** and merged to `develop` (PR #283). All 4 phases' requirements moved to Validated. Post-milestone quick tasks converted the apply mechanism from an EVALSHA Lua script to a Redis Functions library (`FCALL`, ~0 per-call cost, real-Redis-7+ only with a fakeredis root-own-EXPIRE fallback), made the scripts layer stateless, removed dead code (`extract_annotation`, `arun_fcall`), and deferred the cascade-function self-heal to issue #284. Next milestone starts fresh via `/gsd:new-milestone`. — Prior milestone-close note follows.*

*2026-07-09 — Phase 4 complete (final phase of the TTL-cascade milestone): cross-model TTL cascade proven end-to-end on real Redis Stack across every hard graph shape (multi-level, cyclic, self-reference, diamond, shared-child, mixed-special-field child, concurrent-mutation) with one-to-one fakeredis JSON-in-Lua parity, closing the High-priority "no cross-model cascade tests" gap from CONCERNS.md (TEST-01). The `apply.lua` diamond-traversal bug (D-03/D-04) is fixed (boolean visited-set → best-budget-per-node map); `Meta.ttl` is frozen post-`init_rapyer()` with `MetaTtlFrozenError` (D-07); the prior info advisories IN-01/IN-02 are closed. The `CascadeTTL` API, precedence (field > global > `Meta.ttl`), per-child cascading-refresh semantics, and standalone-only Cluster boundary are documented on the docs site + docstrings, with `CascadeDelete`/`CascadeSave` extension-point stubs demonstrating the backbone seam (TEST-02). Verified 8/8 truths; code-review WR-01 (crashing docs example) fixed and re-verified by execution pre-completion. Advisory WR-02 (test freeze-leak) / WR-03 (`init_rapyer` freeze not exception-safe) open for a future robustness pass.*
