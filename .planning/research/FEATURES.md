# Feature Research

**Domain:** Vector/semantic-search (text + embeddings, KNN) inside a Redis ORM (`rapyer` v1.3.6 `RedisText`)
**Researched:** 2026-07-20
**Confidence:** HIGH for the query/index mechanics (grounded in RediSearch docs + redisvl docs + the three VALIDATED spikes); MEDIUM for lifecycle/UX ergonomics (design-note-driven, some judgment calls flagged inline)

Scope note: this covers ONLY the new semantic-search / embedding surface. Existing rapyer machinery (`afind`, the `Expression` tree, Special-Field save/load dispatch, transactional pipelines, `init_rapyer()` lifecycle) is treated as a dependency, not re-researched. Where a feature leans on one of those, it is called out in the **Deps** column.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features any "semantic search over my models" API is assumed to have. Missing = the feature feels broken or toy-grade.

| Feature | Why Expected | Complexity | Deps | Notes |
|---------|--------------|------------|------|-------|
| `RedisText` field storing **one text + one vector** under its own SF key | The whole premise; the atom the milestone is built on | MEDIUM | SF save/load Lua dispatch; HASH storage | Locked decision #7. HASH with `text`, `embedding` (FLOAT32 blob), plus any co-located filter TAGs. |
| `.near('query text', k=...)` KNN clause composing in `afind(...)` | The decided primary query surface; users expect top-k by similarity | MEDIUM | `Expression` tree renders `=>[KNN k @vec $blob]`; `afind` wiring | Renders RediSearch `(*)=>[KNN k @vec $q AS __dist]`, `PARAMS`, `DIALECT 2`. The `.near` node holds the *query text*, which must be embedded client-side before the search fires. |
| Top-level **global similarity method** (search across a model / SF prefix, no boolean filter) | Decided second surface; "just find me the nearest N" without building an `afind` expression | LOW–MEDIUM | Same VECTOR index; wraps the bare `*=>[KNN]` form | Thin wrapper over the same rendering path as `.near`; mostly ergonomics + result hydration. |
| Configurable **k** (number of neighbors) | KNN with a fixed k is unusable | LOW | — | Required param on `.near`/global method. |
| **Return similarity scores/distances** alongside results | Users must rank, threshold, and debug relevance; scoreless KNN is opaque | MEDIUM | Result hydration must surface a field not in the model schema | The `AS __dist` alias comes back as an extra `FT.SEARCH` field. rapyer models are RedisJSON docs — decide how to attach the score to a returned instance (sidecar result object vs. attribute). This is a genuine design point, not free. |
| **Distance metric** declared at field-annotation time (cosine / L2 / IP) | Vector index params are index-time schema; wrong metric = wrong results | LOW | Annotation DSL (mirrors `Index[...]`) | Locked (design note "Implied schema constraint"). Cosine is the sane default for text embeddings. |
| **Embedding dim** declared at annotation time | Must match the model's output size or index creation fails | LOW | Annotation DSL | Locked. Validate dim vs. vectorizer output at `init_rapyer()` (fail-fast). |
| **VECTOR index created over the SF-key prefix** at `init_rapyer()` | KNN needs an index; it must exist before first query | MEDIUM | `init_rapyer()` index lifecycle; new index shape distinct from `idx:{ClassName}` | Locked decision + design note. FLOAT32, declared dim/metric/algo. |
| **Embedding auto-computed on save** (text in → vector persisted) | The ORM promise: users write text, not vectors. Manual vectors defeat the point | HIGH | Vectorizer wired at `init_rapyer()`; write stays atomic (text+vector one pipeline op) | Locked decision #5/#8. Vectorizer runs **client-side before** the write; the write itself is atomic. Async story (thread-offload for local HF vs. native async API vectorizers) is the open question from `questions.md`. |
| **EmbeddingsCache hit avoids recompute** | Re-embedding identical text on every save is slow and (for paid APIs) costly | MEDIUM | redisvl `EmbeddingsCache`, wired via vectorizer `cache=` | redisvl vectorizers accept `cache=`; identical `(text, model_name)` returns the stored vector. Table stakes because recompute-every-save is an obvious footgun. |
| **fakeredis limited to store/cache/serialization; KNN is integration-only** | Correctness of the test story | LOW (policy) | Existing dual test strategy | Locked decision #6. Not a build feature — a testing boundary to encode. |

### Differentiators (Competitive Advantage)

Where rapyer earns its "Redis feels like a real DB" value vs. hand-rolled RediSearch or other Redis ORMs (redis-om has no first-class semantic-search-with-cache-and-lifecycle story).

| Feature | Value Proposition | Complexity | Deps | Notes |
|---------|-------------------|------------|------|-------|
| **Atomic hybrid KNN + boolean prefilter** via `.near(...) & (Model.field == x)` | The headline. Composes semantic + structured filtering in one server-side op with no TOCTOU. This is what "genuine ORM over vectors" means | HIGH | `Expression` tree `& \| ~`; spike-002 Approach A (co-located TAG) | Renders `(@tag:{x})=>[KNN k @vec $q]`, one `FT.SEARCH`. Requires the SF save to **duplicate** the filterable field into the SF HASH and keep it in sync on parent update (the denormalization cost). |
| **Approach-B escape hatch: filter on arbitrary parent-only fields** via a Lua `FT.SEARCH`+`JSON.GET` wrapper | Lets users prefilter on fields they did NOT denormalize, still atomically | HIGH | Lua/`EVALSHA`; spike-002 confirmed `FT.SEARCH` runs inside Lua | Overfetch + N+1 parent `JSON.GET` inside the script. Spike says "keep in back pocket; don't build first." Strong candidate to **defer past v1**. |
| **Distance/score threshold** (range query: "everything within radius r") | Not just top-k, but "all matches better than this cutoff" — common RAG need | MEDIUM | RediSearch `VECTOR_RANGE` syntax; `.near(..., threshold=)` param | `@vec:[VECTOR_RANGE r $q]` is a distinct query form from KNN. Cheap to add if the render layer already exists. Good v1.x. |
| **Batch embedding of many docs on bulk insert** | Embedding one-at-a-time on `ainsert(*models)` is N API calls; `aembed_many` is one | MEDIUM | redisvl `aembed_many(batch_size=)`; existing `ainsert` variadic path | redisvl exposes `embed_many`/`aembed_many`. Wiring bulk-save to batch-embed is a real perf differentiator for ingestion. |
| **Cross-model / global semantic search** returning heterogeneous models | KNN over the SF-key prefix can span multiple model types; resolve each hit back to its parent class | MEDIUM–HIGH | SF-key → parent-class resolution (like module-level `aget` key parsing) | The global method's most powerful form. Needs the returned SF key to carry enough to resolve the owning model. May be v1 in single-model form, cross-model in v1.x. |
| **HNSW tuning knobs** (algorithm FLAT vs HNSW, `EF_RUNTIME`, build params) at annotation time | Lets users trade recall/latency; production vector search demands it | MEDIUM | Annotation DSL; passthrough to index create + query | Locked as annotation-level schema. FLAT is fine/exact for small sets; HNSW for scale. Expose but default sensibly. |
| **EmbeddingsCache TTL coexisting with rapyer TTL cascade** | Avoids the cache growing unbounded; integrates with the milestone-fresh TTL work | MEDIUM | `EmbeddingsCache(ttl=)`; TTL cascade (v1.3.5) | Open question from `questions.md`: does cache TTL participate in cascade or stay independent? Recommend **independent** — the cache is a compute cache, not part of the model aggregate's keyset. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Automatic long-text chunking → multi-vector per field** | "My documents are long, just handle it" | Explodes the data model: one field → N SF keys/vectors, N-to-1 hit→parent resolution, chunk-boundary + re-chunk-on-edit logic, dedup/ranking across chunks. Breaks the clean "one field = one vector under one SF key" invariant. Huge scope | v1: **one text → one vector**, document the model's token limit. Chunking is an application concern (or a future `RedisTextChunks` type). Explicitly defer. |
| **Naive two-step hybrid** (KNN client-side → resolve parents → filter in Python) | Simplest to code | Two round-trips can interleave with other writers → TOCTOU; violates the locked "single atomic op per user action" constraint | Approach A (co-located TAG) or B (Lua). Already decided. |
| **fakeredis-backed KNN tests** | "Unit tests should cover everything" | fakeredis cannot do RediSearch VECTOR/KNN; emulated results would be fiction and give false confidence | Real-Redis-only integration tests on :6370; fakeredis covers store/cache/serialization only. Locked. |
| **rapyer computing embeddings itself / bundling HF+torch in base install** | "Batteries included" | Bloats base install with heavy GPU deps most users don't want; couples rapyer to model-hosting choices | Optional `rapyer[embeddings]` extra wrapping redisvl behind a thin pinned adapter. Locked decision #2. |
| **Storing the vector inline in the parent JSON doc** | "One document, simpler" | Large FLOAT32 arrays bloat every JSON read/write of the parent; can't build a clean VECTOR index over a JSON subpath prefix the way the SF-prefix pattern allows; breaks the SF native-structure convention | SF HASH under its own key. Locked decision #7. |
| **Auto re-embed on *every* save regardless of text change** | "Always fresh" | Wasteful recompute + cache churn when text is unchanged (e.g. TTL refresh, unrelated field update) | Recompute only when the text field actually changed; cache handles identical text. See lifecycle note below. |
| **Exposing raw RediSearch query strings to users** | "Power users want control" | Leaks the abstraction rapyer exists to hide; ties users to RediSearch dialect quirks (`DIALECT 2`, param blobs) | The `.near`/Expression surface. Keep the query string internal. |

---

## Embedding Lifecycle (the non-obvious behavioral spec)

This is the area most likely to be under-specified in requirements, so calling it out explicitly:

1. **On create/save with text set:** embed text (cache-checked) → write text + vector to the SF HASH in the same atomic pipeline op as the parent reference. Vector computed client-side *before* MULTI/EXEC.
2. **On text change:** recompute (cache-checked) and rewrite the vector. **On non-text mutation (or TTL refresh):** do NOT recompute — this is the anti-feature above. Detecting "text changed" needs a dirty-check on the field.
3. **Cache semantics:** `EmbeddingsCache` is keyed `(text, model_name)`, exact-text lookup only, NOT a similarity index (design note #3). It fronts the vectorizer purely to skip recompute. Two rapyer docs with identical text share a cache entry but still each own their SF key/vector.
4. **Batch path:** `ainsert(*models)` should collect texts and call `aembed_many` once, not embed per model.
5. **Model-change / re-index:** switching the embedding model changes dim/metric → invalidates the index and all stored vectors. Treat as a migration, out of scope for v1 (document it).

---

## Feature Dependencies

```
RedisText SF field (text+vector, HASH under SF key)
    └──requires──> SF save/load Lua dispatch (EXISTING)
    └──requires──> transactional pipeline / atomic write (EXISTING)
    └──requires──> vectorizer wired at init_rapyer() (NEW)
                       └──requires──> rapyer[embeddings] extra + redisvl adapter (NEW)
                       └──enhanced-by──> EmbeddingsCache (NEW, redisvl)

VECTOR index over SF-key prefix (NEW, created at init_rapyer)
    └──requires──> annotation-level schema: dim, metric, algo (NEW DSL, mirrors Index[...])
    └──requires──> init_rapyer() index lifecycle (EXISTING pattern, new index shape)

.near() KNN clause + global similarity method
    └──requires──> VECTOR index
    └──requires──> Expression tree render path (EXISTING, extended to emit =>[KNN])
    └──requires──> client-side embed-the-query-text step (NEW)
    └──requires──> result hydration that surfaces the distance score (NEW)

Atomic hybrid KNN + prefilter  ( .near(...) & (Model.field == x) )
    └──requires──> .near() clause
    └──requires──> Expression & | ~ composition (EXISTING)
    └──requires──> co-located filter TAG in SF HASH + sync-on-parent-update (NEW)   [Approach A]

Range/threshold query (VECTOR_RANGE)
    └──enhances──> .near()  (alternate query form, shares render layer)

Batch embedding
    └──enhances──> bulk ainsert (EXISTING variadic path) via aembed_many

Approach-B Lua hybrid (parent-only filters)
    └──requires──> FT.SEARCH-inside-Lua (VALIDATED spike 002)
    └──conflicts-with (choose-one-default)──> Approach A denormalization
```

### Dependency Notes

- **Everything requires the VECTOR index + vectorizer wiring first** — these are the foundational NEW pieces; the query surfaces are meaningless without them. Phase them first.
- **`.near` reuses the Expression tree, but adds a client-side pre-step:** unlike `Model.field == x` (pure string render), `.near('text')` must embed the text before the search can be issued. The Expression node can't be a pure lazy render — it (or `afind`) must trigger embedding. This is the subtlest integration seam with existing `afind`.
- **Hybrid Approach A denormalization is a coupling cost:** any field you want to prefilter on must be copied into the SF HASH and re-synced whenever the parent field changes. This is the price of atomicity-via-single-`FT.SEARCH`. Approach B avoids it but is heavier; they are alternative defaults, not both-at-once.
- **Score surfacing crosses the model/result boundary:** the distance isn't a model field. This needs a decision (sidecar result type vs. injected attribute) shared by both `.near` and the global method.

---

## MVP Definition

### Launch With (v1 — the milestone)

- [ ] **`RedisText` SF field** (text + one FLOAT32 vector, HASH under SF key) — the atom.
- [ ] **Auto-embed on save via redisvl vectorizer + `EmbeddingsCache`**, `rapyer[embeddings]` optional extra, adapter-wrapped — the ORM promise + no-recompute.
- [ ] **Atomic write** (text+vector one pipeline op) — non-negotiable constraint.
- [ ] **Annotation-level vector schema** (dim, metric, algo) + `init_rapyer()`-time validation against vectorizer output.
- [ ] **VECTOR index over SF-key prefix**, created at `init_rapyer()`.
- [ ] **`.near('text', k=...)` KNN clause in `afind`** + **global similarity method** — both decided surfaces.
- [ ] **Similarity score returned** with results.
- [ ] **Atomic hybrid KNN + prefilter (Approach A, co-located TAG)** — the headline differentiator; single `FT.SEARCH`.
- [ ] **Real-Redis-only integration tests** for KNN/index; fakeredis for store/cache/serialization.

### Add After Validation (v1.x)

- [ ] **Distance/score threshold (VECTOR_RANGE)** — add once the render layer is proven; cheap.
- [ ] **Batch embedding on bulk `ainsert`** (`aembed_many`) — add when ingestion throughput becomes a complaint.
- [ ] **Cross-model global semantic search** (heterogeneous hits) — if v1 ships single-model only.
- [ ] **HNSW tuning passthrough** (`EF_RUNTIME`, build params) — expose when users hit scale/recall limits (default FLAT or sane HNSW at launch).
- [ ] **EmbeddingsCache TTL policy** finalized vs. TTL cascade (recommend independent).

### Future Consideration (v2+)

- [ ] **Approach-B Lua hybrid** (arbitrary parent-only prefilters) — the escape hatch; build only when denormalization proves too limiting.
- [ ] **Long-text chunking / multi-vector per field** (`RedisTextChunks`?) — explicitly deferred; large scope, breaks the one-field-one-vector invariant.
- [ ] **Embedding-model migration / re-index tooling** — when users need to switch models without manual teardown.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `RedisText` SF field (text+vector) | HIGH | MEDIUM | P1 |
| Auto-embed on save + cache | HIGH | HIGH | P1 |
| Annotation vector schema + VECTOR index at init | HIGH | MEDIUM | P1 |
| `.near()` KNN in `afind` + global method | HIGH | MEDIUM | P1 |
| Return similarity score | HIGH | MEDIUM | P1 |
| Atomic hybrid KNN + prefilter (Approach A) | HIGH | HIGH | P1 |
| Distance/threshold (VECTOR_RANGE) | MEDIUM | MEDIUM | P2 |
| Batch embedding on bulk insert | MEDIUM | MEDIUM | P2 |
| Cross-model global search | MEDIUM | MEDIUM-HIGH | P2 |
| HNSW tuning passthrough | MEDIUM | MEDIUM | P2 |
| Approach-B Lua hybrid | MEDIUM | HIGH | P3 |
| Long-text chunking / multi-vector | MEDIUM | HIGH | P3 |

---

## Competitor / Prior-Art Feature Analysis

| Feature | redis-om (Python) | Raw RediSearch + redisvl | rapyer's Approach |
|---------|-------------------|--------------------------|-------------------|
| Vector field on a model | Limited/none first-class; users drop to raw index | `SearchIndex` schema, manual HASH/JSON | First-class `RedisText` SF field, auto-managed |
| Auto-embed on save | No | No (you call the vectorizer) | Yes, vectorizer wired at init + cache |
| Hybrid KNN + structured filter | Manual query strings | Manual `(@filter)=>[KNN]` | `.near(...) & (Model.f == x)` Expression composition |
| Atomicity of write + hybrid read | User's problem | User's problem | Guaranteed single server-side op (spike-validated) |
| Score in results | Manual parse | Manual `AS dist` parse | Surfaced on result |

rapyer's edge is the **ORM integration + atomicity guarantee**, not the vector search itself (that's RediSearch's). The differentiation aligns with PROJECT.md Core Value: make Redis feel like a real DB.

## Sources

- `.planning/notes/redistext-design-decisions.md` (locked decisions) — HIGH
- `.planning/spikes/002-hybrid-crosskey-prefilter/README.md` (VALIDATED: hybrid atomic, FT.SEARCH-in-Lua) — HIGH
- `.planning/PROJECT.md` (milestone scope, constraints) — HIGH
- `.planning/research/questions.md` (open lifecycle/async questions) — MEDIUM
- RediSearch vector search docs — KNN `=>[KNN]`, `VECTOR_RANGE`, `EF_RUNTIME`, `DIALECT 2`, hybrid prefilter — HIGH: https://redis.io/docs/latest/develop/ai/search-and-query/query/vector-search/
- redisvl vectorizer + `EmbeddingsCache` docs — `embed_many`/`aembed_many`, `cache=`, `EmbeddingsCache(ttl=)`, `(content, model_name)` keying — HIGH (Context7 `/websites/redis_io_develop_ai`)

---
*Feature research for: RedisText semantic search (rapyer v1.3.6)*
*Researched: 2026-07-20*
</content>
</invoke>
