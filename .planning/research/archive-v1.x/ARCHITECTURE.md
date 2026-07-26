# Architecture Research

**Domain:** TTL-cascade traversal + atomic apply inside `rapyer` (Python async Redis ORM over Redis Stack: RedisJSON + RediSearch)
**Researched:** 2026-07-06
**Confidence:** HIGH (all rapyer claims read directly from source; Redis Cluster / replication / fakeredis claims are HIGH — well-established Redis semantics + corroborated by `.planning/codebase/CONCERNS.md`)

---

## Executive Framing

The milestone's central open decision — **(A) recursive server-side Lua traversal vs (B) Python-side resolution + atomic apply** — comes down to *where the graph walk lives*, not *whether the apply is atomic*. Both approaches can make the actual TTL application (the EXPIRE fan-out) a single atomic server-side unit. The difference is:

- **A** also makes *discovery* atomic, at the cost of baking unbounded per-user-model FK topology into a Lua script and running recursive RedisJSON reads server-side.
- **B** keeps discovery in Python (multi-round-trip, testable, cycle/depth logic trivial) and applies the collected key list atomically via one registered Lua script or one MULTI/EXEC.

**Recommendation: B**, with the apply shaped as a single registered `cascade_ttl_apply` Lua script over a flat key list. Rationale in the comparison section. The deciding factors are (1) the SF-dispatch precedent does *not* generalize cleanly to cascade metadata, (2) Redis Cluster cross-slot and (3) fakeredis Lua+JSON divergence — all of which hit A hardest — and (4) B's traversal generalizes to future delete/save cascade far more safely.

---

## Standard Architecture

### System Overview — where cascade slots into existing rapyer layers

```
┌──────────────────────────────────────────────────────────────────────┐
│  Model/Schema layer  (rapyer/base.py — AtomicRedisModel)              │
│    asave / aget / aupdate / aset_ttl / refresh_ttl                    │
│    __init_subclass__  →  field classification (_relational_field_names,│
│                          _contain_fk, _special_field_names)           │
└───────────────┬───────────────────────────────┬──────────────────────┘
                │ action boundary                │ NEW cascade config detection
                ▼                                 ▼
┌───────────────────────────────┐   ┌──────────────────────────────────┐
│ Actions/TTL layer             │   │  NEW: Cascade backbone            │
│ rapyer/actions.py             │   │  rapyer/cascade/                  │
│  resolve_root_model           │   │   config.py  CascadeSpec /        │
│  register_action_target       │◄──┤             CascadeTTL + global   │
│  flush_action_targets         │   │   planner.py traversal engine     │
│  refresh_ttl(_if_needed)      │   │             (cycle + depth guard) │
└───────────────┬───────────────┘   │   apply.py   per-op apply         │
                │                     └──────────────┬───────────────────┘
                ▼                                    ▼
┌───────────────────────────────┐   ┌──────────────────────────────────┐
│ Field types (rapyer/types/)   │   │ Scripts layer (rapyer/scripts/)   │
│  ForeignKey / RelationalField │   │  registry.py SCRIPT_REGISTRY      │
│   _relational_target (child   │   │  NEW cascade_ttl_apply.lua        │
│    class), target_key         │   │  (EVALSHA, NOSCRIPT self-heal)    │
│  SpecialFieldType.            │   └──────────────┬───────────────────┘
│   special_field_key(key,path) │                  ▼
└───────────────┬───────────────┘   ┌──────────────────────────────────┐
                └────────────────────►  redis.asyncio + RedisJSON        │
                                      │  JSON.MGET (discovery)           │
                                      │  PEXPIREAT (atomic apply)        │
                                      └──────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Grounding in rapyer |
|-----------|----------------|---------------------|
| `CascadeSpec` / `CascadeTTL` (NEW `rapyer/cascade/config.py`) | Value object describing *how* TTL cascades along one FK edge: `depth`, (later) `on_delete`/`on_save`. Global default + per-field override. | Mirrors `RedisConfig.ttl` global (`config.py:45`) + annotation-marker pattern of `Key`/`Index` (`fields/key.py`, `fields/index.py`) |
| Cascade detection in `__init_subclass__` | Populate `_cascade_ttl_fields: dict[field_name -> CascadeTTL]` from FK-field annotations. Additive branch, does **not** reorder existing `safe_issubclass` checks. | Extends existing classification block `base.py:375-403`; CONCERNS.md flags reordering there as fragile |
| Cascade planner (NEW `rapyer/cascade/planner.py`) | Operation-agnostic graph walk from a root model over *cascade-enabled* FK edges; cycle set + max-depth guard; emits a **flat key list**. | Reuses `_all_keys_for_key` (`base.py:559`, classmethod, no fetch), `RelationalFieldType._relational_target` (`relational.py:26`), `ForeignKey.target_key` (`foreign_key.py:44`) |
| Cascade apply strategies (NEW `rapyer/cascade/apply.py`) | Per-operation leaf action over the flat plan. TTL now = `cascade_ttl_apply` EVALSHA / EXPIRE fan-out. DELETE/SAVE later. | TTL apply parallels `refresh_ttl` EXPIRE loop (`base.py:234-242`) and `adelete_by_key` delete fan-out (`base.py:845-857`) |
| `cascade_ttl_apply.lua` (NEW) | Server-side atomic `for key in KEYS/ARGV: PEXPIREAT key, abs_ms`. Registered in `SCRIPT_REGISTRY` so it inherits NOSCRIPT self-heal. | New entry in `SCRIPT_REGISTRY` (`registry.py:28`), invoked via `arun_sha`/`run_sha` (`registry.py:113-135`) |
| Action-boundary integration | `refresh_ttl`/`aset_ttl` expand `_ttl_keys()` → `_cascade_ttl_keys()` when root has cascade-enabled FKs. TTL still resolved once at the root (`resolve_root_model`). | Hook point explicitly named in CONCERNS.md ("extend target registration here rather than duplicating traversal") — `actions.py:89-119` |

---

## Recommended Structure (new files only)

```
rapyer/
├── cascade/                       # NEW cascade-framework backbone
│   ├── __init__.py                # re-export CascadeTTL, CascadeSpec, default setter
│   ├── config.py                  # CascadeSpec (ABC), CascadeTTL, global-default state
│   ├── planner.py                 # CascadePlanner: cycle-safe, depth-guarded traversal → flat keys
│   └── apply.py                   # apply strategies keyed by op kind (TTL now; DELETE/SAVE stubs)
├── fields/
│   └── cascade.py                 # NEW annotation marker `Cascade[...]` (Key/Index-style) — OPTIONAL
│                                  #   if config is attached via Annotated on the FK field
└── scripts/
    ├── constants.py               # + CASCADE_TTL_APPLY_SCRIPT_NAME
    ├── registry.py                # + ("cascade","ttl_apply",CASCADE_TTL_APPLY_SCRIPT_NAME)
    └── lua/
        └── cascade/
            └── ttl_apply.lua      # PEXPIREAT fan-out over the key list
```

### Structure Rationale

- **`rapyer/cascade/` as its own subpackage:** CONCERNS.md is explicit that `AtomicRedisModel` (1331 lines) must not grow further via `__init_subclass__`. Cascade logic lives in narrowly-scoped modules; `base.py` gains only thin `_cascade_ttl_keys()` + a detection branch.
- **planner separate from apply:** the graph walk is *operation-agnostic*; only the leaf action differs per op. This is the extensibility seam for delete/save cascade — they reuse the planner and swap the apply.
- **apply strategy registered as a real Lua script:** so cross-key cascade EXPIRE participates in the same `NOSCRIPT` recovery every other atomic op uses (CONCERNS.md Performance §: "any new cascade Lua scripts … must be registered through registry.py, not hand-rolled EVAL").

---

## The Central Decision: Approach A vs Approach B

### Quick Comparison

| Criterion | A — Recursive server-side Lua | B — Python traversal + atomic apply |
|-----------|-------------------------------|--------------------------------------|
| Discovery atomicity | Atomic (inside script) | Non-atomic (multi round-trip) — **benign for TTL** |
| Apply atomicity | Atomic (same script) | Atomic (one EVALSHA over key list, or MULTI/EXEC) |
| Round trips | 1 EVALSHA | 1 JSON.MGET per BFS level + 1 apply |
| Per-model metadata | Must bake FK-topology + SF-key templates per user model into the script | None — reads live `_relational_target` / `_all_keys_for_key` in Python |
| Cycle detection / depth | Lua `visited` table + depth arg (hard to test) | Python set + int (trivial, unit-testable) |
| Redis Cluster | Fails hard: cross-slot child keys → `CROSSSLOT` | Same cross-slot limit on atomic apply, but **degrades gracefully** (per-slot batches / non-txn pipeline) |
| Replication/AOF | Effects-replication OK **if** using `PEXPIREAT` (absolute) | Same — apply script uses `PEXPIREAT` |
| fakeredis parity | HIGH risk (recursive Lua + `JSON.GET`/cjson reimplementation) | LOW risk (pure-Python walk; apply is a trivial EXPIRE loop) |
| Debuggability | Low (server-side Lua, opaque) | High (Python stack traces) |
| Extends to delete/save | Dangerous (irreversible deletes in Lua, no rollback) | Clean (same planner, swap apply) |
| Build/test complexity | High | Moderate |

### Approach A — detailed

**Shape.** At `init_rapyer()` (after all models are registered), build a Lua metadata literal and splice it into a template at a placeholder — exactly the mechanism `_inject_sf_dispatch` uses for `--[[SF_DISPATCH_TABLE]]` (`registry.py:64-82`):

```
CASCADE_META = {
  ["Author"]    = { fks = {{path="$.publisher", child="Publisher"}}, sf = {".tags"} },
  ["Publisher"] = { fks = {}, sf = {} },
  ...
}
```

The script, from a root `KEYS[1]`: derive model name = split(key, ":")[1] → look up meta → for each FK path `JSON.GET key path` → decode child key string → compute child main + SF keys from `child` meta → `PEXPIREAT` → recurse with a `visited` table and a depth counter.

**Why it is genuinely feasible.** The registration lifecycle already rebuilds scripts after models are known; the SF-dispatch splice proves the injection pattern works; `_all_keys_for_key` shows SF-key derivation is a pure template (`{prefix}:{key}:{dotted_path}`) reproducible in Lua.

**Why it is the weaker choice:**

1. **The SF-dispatch precedent does not generalize.** SF dispatch is keyed on a **finite, closed set of SF *types*** (`SpecialFieldType.__subclasses__()`). Cascade metadata is keyed on an **unbounded, open set of user *model classes*** with per-field FK topology. The injected table grows with the user's schema and must be perfectly consistent with Python's field classification — a second, parallel source of truth for "which paths are cascade FKs / what are a child's SF suffixes." Any drift silently mis-expires or misses keys.
2. **Redis Cluster cross-slot is fatal, with no fallback.** A Lua script may only touch keys hashing to the same slot as its declared `KEYS`. Cascade children have arbitrary keys across slots → `CROSSSLOT`. Inside a single script there is no graceful degradation. (rapyer targets single-node Redis Stack today, but this hard-codes an anti-cluster ceiling.)
3. **fakeredis divergence is the single highest-risk category** per CONCERNS.md ("New Lua-script-based features are the highest-risk category … fakeredis's Lua support is a reimplementation"). Recursive `JSON.GET` + `cjson.decode` + `visited`/depth control is precisely the surface most likely to behave differently under the primary unit-test backend.
4. **RedisJSON-in-Lua ergonomics are error-prone:** `JSON.GET key $.path` returns a JSON-encoded array (`[value]`) that must be `cjson.decode`d and unwrapped, with null/missing/optional-FK handling — the same `[value]` vs `value` variance the loader already patches for (`loader.py` `EXTRACT_*` variants).
5. **Debuggability / delete-safety:** server-side recursion is opaque; and the backbone's whole point is to later carry *delete* cascade — doing irreversible cross-key deletes inside recursive Lua (no rollback) is a footgun.

### Approach B — detailed (recommended)

**Shape.** Two clean phases:

1. **Discovery (Python, `planner.py`).** BFS from the root over cascade-enabled FK edges:
   - For the current frontier of node keys, one `JSON.MGET` projecting each node's cascade-FK JSON paths (reuse the batched load pattern in `rapyer/utils/redis.py` / `execute_load_pipeline`; this is also the documented fix for the N+1 FK concern).
   - Each FK value is a child **key string** (already the on-wire form — `ForeignKey._serialize` returns `_target_key`, `foreign_key.py:136-139`). Resolve the child **class** via the FK field's cached `_relational_target` (`relational.py:26`).
   - Emit the child's full keyset with `child_cls._all_keys_for_key(child_key)` — **no fetch of the child needed** for leaf keys; only intermediate nodes with further cascade FKs are read on the next level.
   - Maintain a `visited: set[str]` (cycle safety) and a per-edge remaining-`depth` (max-depth guard). Skip already-visited keys; stop descending past depth.
   - Output: a de-duplicated flat `list[str]` of every key whose TTL must move.

2. **Apply (server-side, atomic).** Hand the flat list to one registered `cascade_ttl_apply` EVALSHA that runs `PEXPIREAT key, abs_expiry_ms` for every key, inside the caller's `ensure_pipeline` context. One atomic unit; participates in NOSCRIPT recovery.

**Atomicity argument (this is the crux).** The requirement is "the TTL-cascade *propagation* must be a single atomic op … no partial/interleaved application." Propagation = the EXPIRE fan-out, and that **is** one atomic script. Discovery being multi-round-trip does not create a half-expired graph. The only TOCTOU window is *between* reading the child set and expiring it:
- A child **deleted/re-pointed** in that window → `PEXPIREAT` on a missing key is a harmless no-op (returns 0).
- A child **added** in that window → not covered by this cascade, but it is covered by *its own* set-time cascade (the trigger is set-time by design). No orphaned inconsistency.

So the benign TTL semantics let B satisfy the atomicity constraint without paying A's costs. (This argument is TTL-specific; a future *delete* cascade would need to re-examine the window — see backbone section.)

**Why B fits the machinery:**
- Discovery reuses `_relational_target`, `target_key`, `_all_keys_for_key`, and JSON.MGET batching — all existing primitives.
- Apply reuses `ensure_pipeline` (joins the outer transaction if `asave`/`aget` opened one — `context.py:41-62`) and the `resolve_root_model` / `register_action_target` boundary (`actions.py:89-119`), so cascade TTL rides the *same* MULTI/EXEC as the write that triggered it (true set-time atomicity with the parent write).
- Cycle/depth logic is ordinary Python — directly unit-testable, closing the High-priority "no cross-model cascade tests" gap in CONCERNS.md.

**B's honest costs:**
- Extra round trips proportional to graph depth (mitigated by per-level JSON.MGET, not per-node).
- Cross-slot still limits the *atomic* apply in Redis Cluster — but B degrades (split PEXPIREAT by slot into per-slot atomic batches, or accept a non-transactional pipeline) instead of erroring.
- Depends on `_relational_target` name-based resolution (issue #247, CONCERNS.md) — a pre-existing fragility the planner inherits, not one it introduces.

---

## Cycle Detection + Max-Depth Design

**Where it lives:** entirely in `CascadePlanner.traverse()` (Python), never in Lua.

```
def traverse(root) -> list[str]:
    keys: list[str] = list(root._ttl_keys())      # root main + own SF keys
    visited: set[str] = {root.key}
    frontier: list[tuple[key, model_cls, depth_remaining]] = seed_from(root)
    while frontier:
        # one JSON.MGET over frontier node keys, projecting cascade-FK paths
        for (child_key, child_cls, depth) in resolve_children(frontier):
            if child_key in visited or depth <= 0:
                continue                            # cycle guard + depth guard
            visited.add(child_key)
            keys.extend(child_cls._all_keys_for_key(child_key))
            if child_cls has cascade FKs and depth-1 > 0:
                next_frontier.append((child_key, child_cls, depth-1))
    return dedup(keys)
```

- **Cycle safety:** `visited` set of *main keys*; a back-edge to an already-visited node is included once (its keys already collected) and never re-descended. Self-references (`ForeignKey["Self"]`) are handled identically.
- **Max-depth guard:** `depth` comes from the *edge's* `CascadeTTL.depth` (per-field override) or the global default; decremented per hop; `depth <= 0` stops descent. Depth also bounds pathological cycles even if `visited` were bypassed — belt-and-suspenders per the "configurable, cycle-safe traversal depth" requirement.
- **Determinism for replication:** the apply computes one absolute `PEXPIREAT` timestamp (`now + ttl`) *once* and applies it to all keys, so replicas/AOF receive identical expiries regardless of effects-replication timing. Never use relative `EXPIRE` computed per-key inside a loop where drift could matter.

---

## Extensible Backbone Shape (TTL now; delete/save later)

The backbone is **traversal-shared, apply-swapped**:

```
CascadeSpec (ABC)            # rapyer/cascade/config.py
 ├─ CascadeTTL(depth=...)    # implemented this milestone
 ├─ CascadeDelete(...)       # future: on_delete = CASCADE|SET_NULL|RESTRICT
 └─ CascadeSave(...)         # future

CascadePlanner.traverse(root, op) -> Plan   # op-agnostic graph walk (shared)

Apply strategies (keyed by op):
 ├─ TTL   -> cascade_ttl_apply  (PEXPIREAT list)         # now
 ├─ DELETE-> delete list (reuse adelete_by_key fan-out)  # future
 └─ SAVE  -> JSON.SET / asave_special list               # future
```

**Config threading, field-def → traversal:**
1. **Declaration:** per-FK-field via `Annotated` on the reference, e.g. `field: Reference[Author] = Annotated[..., CascadeTTL(depth=3)]`, following the `Key`/`Index` annotation-marker convention (`fields/key.py`, `fields/index.py`). (Alternatively a `Cascade[...]` marker in `rapyer/fields/cascade.py`.)
2. **Detection:** an additive branch in `__init_subclass__` (`base.py:375-403`) records `_cascade_ttl_fields: dict[str, CascadeTTL]`. **Do not reorder** existing `safe_issubclass` checks (CONCERNS.md fragile area).
3. **Default merge:** at `init_rapyer()`, a global default `CascadeTTL` (settable like `init_rapyer(ttl=...)`, `init.py:45`) fills fields without an explicit override — same "global default + per-field override" model the milestone specifies. Assigned onto each model class alongside `Meta.ttl`.
4. **Consumption:** `CascadePlanner` reads `_cascade_ttl_fields[field] .depth` + the FK's `_relational_target` to decide which edges to follow and each child's class.

**Design invariants that keep future ops safe:**
- All target discovery goes through the planner + `resolve_root_model`; never touch `EXPIRE`/`DELETE` directly (CONCERNS.md: bypassing `resolve_root_model` reintroduced a whole bug class).
- All SF-key derivation goes through `_all_keys_for_key` / `_iter_special_fields` — never re-implement top-level-only iteration (the recurring nested-SF bug class, CONCERNS.md).
- The planner returns a *plan of keys/models*, decoupled from what the apply does — so delete-cascade reuses it verbatim, only substituting a delete apply (and re-examining the TOCTOU window, since delete is not idempotent-benign like EXPIRE).

---

## Data Flow

### Set-time cascade (recommended B), inside the triggering write's transaction

```
asave() / aget() / aset_ttl()  ──(mark_actions outer boundary)──►
  flush_action_targets  ──►  resolve_root_model(root)
        │
        ▼
  root.refresh_ttl(can_use_pipeline=True)
        │   (if root has cascade-enabled FKs)
        ▼
  CascadePlanner.traverse(root)                      [Python discovery]
     ├─ JSON.MGET frontier level 1 (cascade FK paths)     ── round trip
     ├─ resolve child class via _relational_target
     ├─ child_cls._all_keys_for_key(child_key)  (no fetch)
     ├─ JSON.MGET frontier level 2 …                       ── round trip
     └─ visited set + depth guard  →  flat key list
        │
        ▼
  ensure_pipeline(root.Meta)  (joins the SAME MULTI/EXEC as the write)
     └─ run_sha(cascade_ttl_apply, keys=N, *keys, abs_expiry_ms)   [atomic apply]
        └─ Lua: for k in KEYS: PEXPIREAT k abs_ms
```

Backward compatibility: a root with **no** cascade config takes the existing path (`refresh_ttl` over `_ttl_keys()` only) — the planner is only consulted when `_cascade_ttl_fields` is non-empty, so `Meta.ttl`/`refresh_ttl` and the `TwoModelDeleteBase` "no cascade" assertions remain unchanged.

---

## Scaling Considerations

| Scale | Adjustment |
|-------|------------|
| Small graphs (depth ≤ 3, few children) | B's per-level JSON.MGET is 1–3 round trips + 1 apply; negligible |
| Wide fan-out (many children per node) | Single JSON.MGET per level already batches; apply is one EVALSHA over N keys — watch very large `KEYS[]` arrays (chunk if beyond a sane cap, mirroring `max_delete_per_transaction`, `config.py:57`) |
| Redis Cluster | Atomic-across-slots impossible for both A and B; B degrades to per-slot atomic batches or documented non-atomic fan-out. Treat single-slot atomicity as a documented guarantee only for non-cluster / hash-tagged deployments |

### First bottleneck
Round trips scale with graph *depth*, not node count (per-level MGET). Deep chains are the cost; cap via `CascadeTTL.depth`.

---

## Anti-Patterns

### Baking user-model FK topology into a monolithic Lua script "because SF dispatch does it"
**Why wrong:** SF dispatch is a closed set of *types*; cascade metadata is an open set of *user models* and a second source of truth prone to drift. **Instead:** read live Python metadata (`_relational_target`, `_cascade_ttl_fields`, `_all_keys_for_key`) at traversal time.

### Making the discovery phase try to be atomic
**Why wrong:** For TTL, discovery TOCTOU is benign (EXPIRE-on-missing is a no-op; new nodes self-cover at their own set-time). Chasing discovery atomicity is what forces you into the fragile all-Lua design. **Instead:** only the apply is atomic.

### Hand-rolling EXPIRE/DELETE fan-out outside the script registry
**Why wrong:** bypasses NOSCRIPT self-heal and `resolve_root_model` centralization — both documented bug classes in CONCERNS.md. **Instead:** register `cascade_ttl_apply` in `SCRIPT_REGISTRY`; route targets through `register_action_target`.

### Re-implementing special-field key iteration inside cascade code
**Why wrong:** the recurring nested-SF bug class (fixed in 1.3.3) came from top-level-only iteration. **Instead:** always use `_all_keys_for_key` / `_iter_special_fields`.

### Testing cascade only against fakeredis
**Why wrong:** the apply Lua and RedisJSON reads are the highest fakeredis-divergence risk. **Instead:** integration tests against `real_redis_client`, per CONCERNS.md.

---

## Integration Points / Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| planner ↔ FK types | reads `_relational_target`, `target_key` | inherits issue #247 name-resolution fragility |
| planner ↔ model class | `_all_keys_for_key`, `_cascade_ttl_fields`, `_iter_special_fields` | classmethods/state, no instance fetch for leaf keys |
| apply ↔ scripts | `run_sha`/`arun_sha` on `cascade_ttl_apply` | NOSCRIPT recovery inherited |
| cascade ↔ action boundary | `refresh_ttl`/`aset_ttl` expand to `_cascade_ttl_keys()`; `resolve_root_model` unchanged | single-place TTL rule preserved |
| cascade ↔ pipeline | `ensure_pipeline` joins outer MULTI/EXEC | cascade rides the triggering write's transaction |
| config ↔ init | global-default `CascadeTTL` assigned at `init_rapyer()` like `Meta.ttl` | per-field override wins |

---

## Recommended Build Order (dependency-ordered)

1. **Config + detection backbone (no behavior).** `CascadeSpec`/`CascadeTTL` in `rapyer/cascade/config.py`; global-default state + `init_rapyer` wiring; annotation marker + additive `__init_subclass__` branch populating `_cascade_ttl_fields`. Unit tests for classification (guard the fragile `__init_subclass__` area). *Blocks everything.*
2. **Planner (Python traversal).** Cycle set + depth guard + per-level JSON.MGET; reuse `_relational_target` / `_all_keys_for_key`. Heavy unit + integration tests incl. cycles, self-refs, depth caps, missing children. *This is the risky logic — test hardest; depends on 1.*
3. **Atomic apply.** `cascade_ttl_apply.lua` (PEXPIREAT absolute) + `constants.py` + `SCRIPT_REGISTRY` entry; `apply.py` TTL strategy. Real-Redis + fakeredis parity tests. *Depends on 2.*
4. **Action-boundary wiring.** `_cascade_ttl_keys()`; expand `refresh_ttl`/`aset_ttl` when cascade-enabled; ensure it joins the triggering write's pipeline. Backward-compat regression: no-config path unchanged; confirm `TwoModelDeleteBase` still holds. *Depends on 3.*
5. **Cascade integration test suite.** New `tests/integration/foreign_keys/` (+ `tests/models/foreign_key_types.py` fixtures) covering multi-level, cyclic, mixed-SF-child, cluster-note cases — closes the High-priority CONCERNS.md gap.
6. **Docs + backbone stubs.** `docs/documentation/special-fields/` cascade page; leave `CascadeDelete`/`CascadeSave` as documented, unimplemented extension points to prove the seam.

---

## Sources

- rapyer source (read directly, HIGH): `rapyer/base.py` (`_all_keys_for_key` :559, `_iter_special_fields` :763, `_ttl_keys` :779, `refresh_ttl` :234, `aset_ttl` :548, `asave` :469, `aget_or_create` :796, `__init_subclass__` classification :375-403), `rapyer/actions.py` (`resolve_root_model` :89, `register_action_target` :104, `flush_action_targets` :157), `rapyer/context.py` (`ensure_pipeline` :41), `rapyer/scripts/registry.py` (`SCRIPT_REGISTRY` :28, `_inject_sf_dispatch` :64, `arun_sha` :118), `rapyer/scripts/loader.py`, `rapyer/scripts/lua/atomic/get_or_create.lua`, `rapyer/types/foreign_key.py` (`_serialize` :136, `target_key` :44), `rapyer/types/relational.py` (`_relational_target` :26, `resolve_relational_targets` :93), `rapyer/types/special.py` (`special_field_key` :24), `rapyer/config.py`.
- `.planning/codebase/CONCERNS.md` (HIGH): fakeredis/real-Redis Lua divergence as highest-risk category; `resolve_root_model`/nested-SF bug classes; "register cascade Lua through registry.py"; missing cross-model cascade tests (High priority); N+1 FK batching fix via JSON.MGET.
- `.planning/PROJECT.md`, `.planning/codebase/ARCHITECTURE.md` (HIGH): atomicity mechanics, FK-as-inline-key-string, set-time-only cascade rationale.
- Redis semantics (HIGH, established): Lua scripts / MULTI-EXEC require same hash slot in Cluster (`CROSSSLOT`); effects-based script replication + `PEXPIREAT` for deterministic expiry across replicas/AOF.

---
*Architecture research for: rapyer TTL-cascade traversal + atomic apply*
*Researched: 2026-07-06*
