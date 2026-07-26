# Architecture Research

**Domain:** RedisText — text + vector-embedding special field with KNN semantic search, integrated into the existing rapyer Redis ORM
**Researched:** 2026-07-20
**Confidence:** HIGH (grounded against real rapyer internals + three VALIDATED spikes; redisvl API confidence MEDIUM — pin/adapter required, see spike 003)

## Standard Architecture

### System Overview (integration view)

```
┌───────────────────────────────────────────────────────────────────────┐
│                  User model: class Article(AtomicRedisModel)            │
│    body: RedisText[Vector(dim=384, metric="cosine", algo="hnsw")]      │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │ __init_subclass__ classifies as SF
                                 │ (already: _special_field_names / _contain_sf)
                                 ▼
┌───────────────────────────────────────────────────────────────────────┐
│  RedisText  (NEW SpecialFieldType)          rapyer/types/redis_text.py  │
│  - holds text + (cached) embedding + co-located TAG mirror              │
│  - asave_special(): HSET text, embedding(f32 blob), parent, tags        │
│  - aset_text(): recompute vector (via adapter) → re-HSET                │
│  - near(query, k=...) → NearExpression                                  │
└───────┬───────────────────────────────┬───────────────────────────────┘
        │ writes ride ensure_pipeline    │ vector computed BEFORE pipeline
        ▼                                ▼
┌──────────────────────┐   ┌──────────────────────────────────────────────┐
│ Embedding adapter     │   │ VECTOR index manager (NEW init step)          │
│ (NEW, rapyer/         │   │ rapyer/vector/index.py                        │
│  embeddings/*)        │   │ - FT.CREATE ON HASH over SF-key prefix        │
│ - redisvl vectorizer  │   │ - VECTOR field + co-located TAGs              │
│ - EmbeddingsCache     │   │ - registered in init_rapyer() alongside       │
│   (3rd keyspace)      │   │   acreate_index() (but separate shape)        │
└──────────┬───────────┘   └──────────────────────┬───────────────────────┘
           │                                       │
           ▼                                       ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    Redis Stack (:6370, real-Redis-only)                 │
│  ┌──────────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │
│  │ Parent JSON doc   │  │ SF HASH               │  │ EmbeddingsCache   │  │
│  │ Article:{pk}      │  │ __rapyer_special__:   │  │ {name}:sha256(txt)│  │
│  │  $.body_ref → SF  │  │  Article:{pk}:body    │  │  {content,        │  │
│  │  (index: idx:     │  │  {text, embedding,    │  │   embedding, meta}│  │
│  │   Article, JSON)  │  │   parent, <tags>}     │  │  (dedup only)     │  │
│  │                   │  │  (index: idx:vec:...,│  │                   │  │
│  │                   │  │   HASH + VECTOR)      │  │                   │  │
│  └──────────────────┘  └──────────────────────┘  └──────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities (NEW vs MODIFIED)

| Component | Responsibility | New / Modified | File(s) |
|-----------|----------------|----------------|---------|
| `RedisText` SF type | Store text + embedding + parent ref + co-located TAG mirror under its own HASH key; expose `asave_special`/`adelete_special`/`aduplicate_special` + `aset_text` + `near()` | **NEW** | `rapyer/types/redis_text.py` |
| `Vector(...)` annotation | Declare index-time schema (dim, metric, algo, FLOAT32, HNSW params) at the field level; validated at class-build / init | **NEW** | `rapyer/fields/vector.py` |
| Embedding adapter | Thin, version-pinned wrapper over a redisvl vectorizer + `EmbeddingsCache`; async `aembed(text)` returning a float32 vector, cache-first | **NEW** | `rapyer/embeddings/adapter.py` |
| VECTOR index manager | Build/drop the `ON HASH` VECTOR index over the SF-key prefix; distinct shape from `idx:{ClassName}` | **NEW** | `rapyer/vector/index.py` |
| `NearExpression` | Render KNN + hybrid RediSearch syntax; compose with boolean `Expression`s via `&`/`|`/`~` | **NEW** | `rapyer/fields/expression.py` (extend) |
| Global similarity method | Top-level `asearch_near(...)` / model-level KNN entrypoint; resolves SF keys → parent models | **NEW** | `rapyer/base.py` (module fn) + `rapyer/vector/search.py` |
| `init_rapyer()` | Also register the VECTOR index(es) + wire the vectorizer/cache instance onto `Meta` (like `Meta.redis`) | **MODIFIED** | `rapyer/init.py` |
| `RedisConfig` (`Meta`) | Hold `vectorizer`/`embeddings_cache` handles (freeze-aware) | **MODIFIED** | `rapyer/config.py` |
| `_search_keys_by_query` / afind query path | Pass `PARAMS 2 <blob>` + `DIALECT 2`; target the VECTOR index when a `NearExpression` is present | **MODIFIED** | `rapyer/base.py` |
| `redis_schema()` | Unchanged for JSON index; RedisText stays **excluded** from it (SF fields are, by design) — VECTOR schema built on a separate path | **UNCHANGED (rely on existing exclusion)** | `rapyer/base.py` |
| Lua FT.SEARCH fallback | `EVALSHA` script: KNN overfetch → per-candidate parent `JSON.GET` + filter, for parent-only prefilters | **NEW (escape hatch, defer)** | `rapyer/scripts/lua/vector/hybrid_search.lua` |

## Recommended Project Structure

```
rapyer/
├── types/
│   └── redis_text.py        # RedisText(SpecialFieldType) — HASH store, save path, near()
├── fields/
│   ├── vector.py            # Vector[...] annotation + param validation
│   └── expression.py        # + NearExpression (extend existing tree)
├── embeddings/              # NEW package — optional extra rapyer[embeddings]
│   ├── __init__.py
│   ├── adapter.py           # redisvl vectorizer + EmbeddingsCache wrapper (pinned)
│   └── protocol.py          # Vectorizer/Cache Protocols so redisvl is swappable
├── vector/                  # NEW package — real-Redis-only index+query machinery
│   ├── index.py             # VECTOR index create/drop over SF-key prefix
│   └── search.py            # KNN query render + SF-key→parent resolution
└── scripts/lua/vector/
    └── hybrid_search.lua    # Approach-B Lua fallback (parent-only prefilter) — deferred
```

### Structure Rationale

- **`embeddings/` isolated behind an extra:** heavy deps (numpy always; torch/HF only with local vectorizers) load only when `rapyer[embeddings]` is installed. A `protocol.py` keeps the adapter swappable and contains the redisvl-version drift observed in spike 003 (`text`→`content`).
- **`vector/` separate from `types/`:** the index+query machinery is real-Redis-only by design (fakeredis unsupported for VECTOR/KNN). Isolating it keeps the fakeredis unit path (store/cache/serialization) importable without a live index.
- **`NearExpression` in the existing `expression.py`:** it must compose with `AndExpression`/`OrExpression`/`NotExpression` via the same `&`/`|`/`~` operators, so it belongs in the same tree — but it is *not* a plain `ExpressionField` operator (KNN is a query modifier, not a boolean leaf).

## Architectural Patterns

### Pattern 1: SF-as-HASH riding the transactional pipeline (mirror RedisSet)

**What:** `RedisText.asave_special()` writes the HASH (`text`, `embedding` float32 blob, `parent`, co-located TAG mirror) through `self.client`, which is pipeline-aware. `asave`/`ainsert` already iterate `_iter_special_fields()` and call `asave_special()` *inside* `ensure_pipeline(self.Meta)`, so the parent `$.body_ref` JSON.SET and the SF HASH land in one MULTI/EXEC — exactly like `RedisSet.asave_special` (`rapyer/types/redis_set.py:226`).
**When to use:** the DECIDED save path. No bespoke Lua required for save (spike 001 proved atomic combined write; the pipeline achieves the same atomicity for a set-time write).
**Trade-offs:** the vector must exist *before* the pipeline opens — embedding compute is an `await` that cannot live inside MULTI/EXEC. So the flow is: (1) compute/lookup vector (async, outside pipeline), (2) stash on the field instance, (3) pipeline write serializes the stashed blob. This is the "atomicity boundary" from the design note (decision 5/8): text→vector is outside Redis; text+vector write is atomic.

**Example:**
```python
class RedisText(SpecialFieldType):
    LUA_SNIPPET_DIR = None  # save rides the pipeline, not get_or_create.lua

    async def asave_special(self):
        # self._embedding was populated by aset_text/adapter BEFORE the pipeline
        await self.client.hset(self.special_key, mapping={
            "text": self._text,
            "embedding": _to_f32_blob(self._embedding),
            "parent": self.key,               # SF-key → parent resolution
            **self._tag_mirror,               # co-located prefilter fields (spike 002 A)
        })
```

### Pattern 2: Separate VECTOR index shape over the SF-key prefix

**What:** A new index distinct from `idx:{ClassName}`: `FT.CREATE idx:vec:{ClassName}:{field} ON HASH PREFIX 1 __rapyer_special__:{ClassName}: SCHEMA embedding VECTOR {algo} 6 TYPE FLOAT32 DIM {dim} DISTANCE_METRIC {metric} parent TAG <co-located tags>`. Built in `init_rapyer()` on a **new** branch, not through `redis_schema()`/`acreate_index()` (which deliberately *skips/raises* on SpecialFieldType — `rapyer/base.py:283`).
**When to use:** once per RedisText field type at init, real-Redis only (guard with `is_fake_redis`, like the cascade-function registration in `init.py`).
**Trade-offs:** the SF-key prefix `__rapyer_special__:{ClassName}:` also matches *other* SF fields (RedisSet HASHes/SETs) on the same model. An `ON HASH` VECTOR index will ignore non-HASH keys, but a RedisSet stored as a HASH-like structure or a second RedisText field on the same model would collide. **Flag:** scope the prefix more tightly (include a discriminator segment, e.g. a per-field-type key namespace or a `__rapyer_vec__:` prefix) or add a TAG discriminator the index filters on. This is the single most important integration decision for the index phase.

### Pattern 3: KNN as a query modifier composing with the boolean tree

**What:** `NearExpression` renders the prefilter (existing boolean `Expression`s over co-located TAG fields in the SF HASH) plus the KNN clause: `(<prefilter>)=>[KNN {k} @embedding $blob AS __dist]`. The prefilter half reuses `EqExpression`/`AndExpression.create_filter()` verbatim; the KNN half is appended. The query blob is passed via `PARAMS 2 blob <f32-bytes>` with `DIALECT 2` — both currently **absent** from `_search_keys_by_query` (`rapyer/base.py:965`), which must be extended to accept params/dialect and to target the VECTOR index.
**When to use:** `afind(Article.body.near("query text", k=10) & (Article.category == "ai"))` and the global `asearch_near(...)`.
**Trade-offs:** `.near()` returns a node that is *terminal* for KNN — you can AND/OR/NOT the prefilter around it, but only one KNN clause per query (RediSearch constraint). The result rows are SF keys carrying `parent`; resolve to parent models via the existing `fetch_models_with_sf_loads`/`build_models_from_dumps` path after mapping `parent` → parent key.

**Example:**
```python
class NearExpression(Expression):
    def __init__(self, field_name, query_text, k, prefilter: Expression | None = None):
        ...
    def create_filter(self) -> str:
        pre = self.prefilter.create_filter() if self.prefilter else "*"
        return f"({pre})=>[KNN {self.k} @{self.field_name} $blob AS __dist]"
    # blob (f32 bytes) surfaced separately to the search call as PARAMS
```

### Pattern 4: EmbeddingsCache as a cache-aside third keyspace

**What:** The adapter checks `EmbeddingsCache` (`{name}:{sha256(content)}`, keyed on content+model_name) before calling the vectorizer; on miss it computes and `aset`s. It is *not* the source of truth for a field's vector (that's the SF HASH) — purely recompute-avoidance (design decision 3, spike 003).
**When to use:** every `aset_text`/save that needs an embedding.
**Trade-offs:** three keyspaces now coexist (parent JSON, SF HASH, cache). Cache TTL is independent of `Meta.ttl`; spike 003 confirms per-entry TTL works if alignment is later desired. Target the **0.23.0** API (`content=`, not `text=`) behind the adapter.

## Data Flow

### Save path (text set / model save)

```
model.body.aset_text("...")  OR  model.asave()
    ↓
adapter.aembed(text):  cache.aget(sha256) ─hit→ vector
                                          └miss→ vectorizer(text) → cache.aset → vector
    ↓  (await completes BEFORE pipeline opens)
field._text/_embedding/_tag_mirror stashed on instance
    ↓
async with ensure_pipeline(Meta):        # MULTI
    pipe_json.set(key, "$.body_ref", sf_key)   # parent doc reference
    field.asave_special()  → HSET sf_key {text, embedding, parent, tags}
                                          # EXEC on context exit — atomic set-time write
```

### Index path (init_rapyer)

```
init_rapyer(redis, vectorizer=..., embeddings_cache=...)
    ↓
existing: per-model acreate_index() for JSON Index[...] fields (unchanged)
    ↓
NEW: for each model with a RedisText field, if not is_fake_redis:
        drop+create idx:vec:{Class}:{field} ON HASH over SF prefix
        (VECTOR + co-located TAG schema from the Vector[...] annotation)
    ↓
NEW: Meta.vectorizer / Meta.embeddings_cache assigned (freeze-aware, like Meta.redis)
```

### Query path (KNN + hybrid prefilter)

```
afind(Article.body.near("q", k=10) & (Article.category == "ai"))
    ↓
combine expressions → NearExpression.create_filter():  "(@category:{ai})=>[KNN 10 @embedding $blob AS __dist]"
    ↓
adapter.aembed("q") → f32 blob  (query vector; cache-first)
    ↓
ft(idx:vec:...).search(Query(qs).sort_by("__dist").dialect(2), query_params={"blob": blob})
    ↓                              # single FT.SEARCH — atomic (spike 002 approach A, default)
result docs = SF keys; read `parent` field → parent keys
    ↓
fetch_models_with_sf_loads + build_models_from_dumps → list[Article]   (existing machinery)

# Escape hatch (parent-only prefilter, no denormalization): approach B
# EVALSHA hybrid_search.lua → FT.SEARCH KNN overfetch + per-candidate JSON.GET filter
# (spike 002 proved FT.SEARCH is callable inside Lua). Defer; build A first.
```

### State Management / sync-on-change

- **Text changes ⇒ vector recompute.** SF fields cannot be mutated via `aupdate` (`UpdateAtomicModelError` guards `_special_field_names`). RedisText must expose its own `aset_text(...)` that recomputes the embedding and re-HSETs — never a bare attribute assignment.
- **Co-located TAG drift (spike 002 approach A tradeoff).** Filterable parent fields duplicated into the SF HASH must be re-synced whenever the parent changes them. Either RedisText owns those fields, or the parent's `asave`/`aupdate` must re-write the SF TAG mirror. **Flag** this coupling for the query phase — approach B (Lua) avoids it at the cost of overfetch + N+1 `JSON.GET`.

## Anti-Patterns

### Anti-Pattern 1: Routing the VECTOR index through `redis_schema()`/`acreate_index()`

**What people do:** Try to make RedisText emit a `VectorField` from `redis_schema()` like `RedisInt` emits `NumericField`.
**Why it's wrong:** `redis_schema()` deliberately **excludes** `SpecialFieldType` and raises `UnsupportedIndexedFieldError` if an SF field carries `Index[...]` (`rapyer/base.py:283-288`). The JSON index is over the parent-doc prefix; the vector lives in a separate HASH key. Forcing it in would either raise or index the wrong prefix.
**Do this instead:** Build the VECTOR index on a dedicated `vector/index.py` path over the SF-key prefix, `ON HASH`, called separately in `init_rapyer()`.

### Anti-Pattern 2: Computing the embedding inside the pipeline / a Lua script

**What people do:** Try to make the whole text→vector→store one server-side atomic op.
**Why it's wrong:** Embedding is an external compute (local HF model or remote API); it cannot run inside MULTI/EXEC or a Lua `EVALSHA`. Attempting it breaks the "no read-then-branch mid-transaction" pipeline limit and the atomicity model.
**Do this instead:** Compute the vector client-side *before* the pipeline (cache-first via the adapter), stash it on the field, then let `asave_special()` write the stashed blob inside the transaction. Atomicity applies to the *write*, not the compute (design decision 5).

### Anti-Pattern 3: Two-step hybrid query (KNN, then resolve parents, then filter)

**What people do:** KNN search → fetch parents → filter in Python.
**Why it's wrong:** Two round-trips can interleave with other writers (TOCTOU); violates "every user action is one atomic server-side op" (design decision 8).
**Do this instead:** Co-locate prefilter fields in the SF HASH so one `FT.SEARCH` does KNN+prefilter (approach A, default). For parent-only fields, use the Lua `FT.SEARCH`-in-`EVALSHA` fallback (approach B), still one `EVALSHA`.

### Anti-Pattern 4: Adding redisvl to the base dependency set

**What people do:** `import redisvl` at module top in `rapyer/types/redis_text.py`.
**Why it's wrong:** redisvl (and its numpy/torch/HF tail) must stay behind the `rapyer[embeddings]` extra; a top-level import breaks base installs. redisvl's API also drifts across minors (spike 003: `text`→`content` between 0.7.0 and 0.23.0).
**Do this instead:** Import redisvl only inside the `embeddings/adapter.py` (lazily / guarded), behind a `Protocol`, version-pinned, with a clear ImportError message pointing at the extra.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| redisvl vectorizer | Lazy import behind `embeddings/adapter.py`, `rapyer[embeddings]` extra | Pin version; target 0.23.0 API (`content=`); wrap in a Protocol to contain drift |
| redisvl `EmbeddingsCache` | Cache-aside, third keyspace `{name}:{sha256(content)}` | Async ops validated (spike 003); per-entry TTL works; dedup only, not source of truth |
| Redis Stack RediSearch VECTOR | `FT.CREATE ON HASH` over SF prefix + `FT.SEARCH` with `PARAMS`/`DIALECT 2` | Real-Redis-only (:6370, RediSearch 2.10); fakeredis unsupported by design |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `RedisText` ↔ `ensure_pipeline`/`self.client` | Same SF contract as RedisSet (`asave_special` rides the active pipeline) | No new pipeline machinery needed |
| `NearExpression` ↔ existing `Expression` tree | `&`/`|`/`~` compose prefilter around the KNN clause | KNN is terminal/one-per-query; blob passed as PARAMS, not inside the string |
| Query path ↔ VECTOR index | `_search_keys_by_query` extended: params + dialect + index selection | Must branch to `idx:vec:...` when a `NearExpression` is present |
| `init_rapyer()` ↔ VECTOR index + Meta wiring | New init branch, guarded by `is_fake_redis`, after existing JSON-index creation | Mirror the cascade-function `is_fake_redis` guard already in `init.py` |
| SF-key → parent | HASH `parent` field → parent key → existing fetch machinery | Spike 001 confirmed resolution |

## Suggested Build Order (type → index → query)

1. **Embedding adapter + extra (foundation).** `rapyer[embeddings]` extra; `embeddings/adapter.py` wrapping redisvl vectorizer + `EmbeddingsCache` behind Protocols, pinned to the 0.23.0 API. Unit-testable on fakeredis (cache round-trip, dummy vectors) — no VECTOR index needed. De-risked by spike 003.
2. **`Vector[...]` annotation + `RedisText` SF type + save path.** Annotation carries dim/metric/algo/FLOAT32/HNSW params (validated at class-build/init). `RedisText.asave_special` HSETs text+blob+parent+tags riding `ensure_pipeline`; `aset_text` recomputes via the adapter. Fakeredis-testable for store/serialization; real-Redis for the HASH write. Depends on (1). De-risked by spike 001.
3. **VECTOR index manager + `init_rapyer()` wiring.** New `vector/index.py`; create/drop `ON HASH` index over the (tightly-scoped — see Pattern 2 flag) SF prefix; wire vectorizer/cache onto `Meta` (freeze-aware). Real-Redis-only, guarded by `is_fake_redis`. Depends on (2) for the key shape + annotation params.
4. **KNN query surface (default: co-located TAG hybrid).** `NearExpression` + extend `_search_keys_by_query` for `PARAMS`/`DIALECT 2` + VECTOR-index selection; global `asearch_near(...)`; SF-key→parent resolution reusing existing fetch machinery. Co-located TAG prefilter (approach A). Depends on (3). De-risked by spike 002.
5. **Lua `FT.SEARCH` fallback (escape hatch, may defer).** `hybrid_search.lua` `EVALSHA` for parent-only prefilters (KNN overfetch + N+1 `JSON.GET`). Register via existing scripts machinery. Build only if parent-only filtering without denormalization is required this milestone. Spike 002 proved feasibility.

**Ordering rationale:** the adapter is a leaf dependency of the save path; the save path defines the SF-key/HASH shape the index must target; the index must exist before any KNN query can run. Steps 1–2 are the only fakeredis-testable slices; 3–5 are integration-only (real Redis :6370). Step 5 is optional/deferrable — the co-located TAG default (step 4) satisfies the atomic-hybrid requirement on its own.

## Open Flags for Roadmap / Phase Research

- **Index prefix scoping (Pattern 2):** the biggest unresolved integration decision. `__rapyer_special__:{Class}:` collides with other SF fields and with multiple RedisText fields on one model. Decide a discriminator (dedicated `__rapyer_vec__:` namespace, or a per-field TAG the index filters) in the index phase.
- **Index granularity:** one index per (model, field) vs one shared cross-model index per (dim, metric). Cross-model global KNN (design decision 4, "global similarity method") argues for a shared index keyed by a `parent`/`model` TAG; per-field is simpler. Resolve in step 3.
- **`Meta` freeze interaction:** `RedisConfig` freezes after init (`_meta_locked`). Vectorizer/cache handles must be assigned during the unfrozen window in `init_rapyer()` (like `Meta.redis`) — confirm they are plan-inputs vs derived (cf. `cascade_function_name` exemption).
- **TAG mirror re-sync on parent update:** approach A requires the parent's `asave`/`aupdate` to re-write co-located SF TAG fields. Define who owns that write in step 4.
- **`init.py` merge markers:** the working-tree `rapyer/init.py` currently contains unresolved `<<<<<<< HEAD` conflict markers — the shipped (origin/develop) branch is the second block. Not a RedisText concern, but the init changes in step 3 must land on the resolved file.

## Sources

- rapyer internals (HIGH): `rapyer/types/special.py`, `rapyer/types/redis_set.py`, `rapyer/base.py` (`redis_schema`/`acreate_index`/`afind`/`_search_keys_by_query`/`create_expressions`), `rapyer/fields/expression.py`, `rapyer/fields/index.py`, `rapyer/config.py`, `rapyer/init.py`, `rapyer/scripts/registry.py`
- `.planning/spikes/001-vector-knn-sf-key/README.md` (VALIDATED — KNN over SF prefix, HASH storage, atomic combined save)
- `.planning/spikes/002-hybrid-crosskey-prefilter/README.md` (VALIDATED — co-located TAG default; FT.SEARCH callable in Lua)
- `.planning/spikes/003-redisvl-embeddingscache-async/README.md` (VALIDATED — async EmbeddingsCache; 0.23.0 API drift)
- `.planning/notes/redistext-design-decisions.md`, `.planning/PROJECT.md`

---
*Architecture research for: RedisText integration into rapyer*
*Researched: 2026-07-20*
