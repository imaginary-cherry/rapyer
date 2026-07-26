# Pitfalls Research

**Domain:** Adding a text+embedding special field (`RedisText`) with RediSearch VECTOR/KNN search to an existing Redis ORM (`rapyer`, brownfield)
**Researched:** 2026-07-20
**Confidence:** HIGH (RediSearch vector mechanics verified against Redis docs + redisvl docs; ORM-specific pitfalls derived from the codebase's own CONCERNS.md and design notes)

> Phase numbers below are logical groupings for the v1.3.6 roadmap (phases continue from Phase 5). They map to the natural build order: **(A) SF store/HASH + FLOAT32 serialization**, **(B) embedding adapter + EmbeddingsCache extra**, **(C) VECTOR index lifecycle in `init_rapyer()`**, **(D) KNN query surface + atomic hybrid**, **(E) test strategy / CI / version matrix**. Substitute real phase IDs when the roadmap is cut.

## Critical Pitfalls

### Pitfall 1: FLOAT32 blob encoding — dtype, endianness, and dim mismatch

**What goes wrong:**
The vector written to the HASH field and the vector passed in the KNN `PARAMS` blob must be **raw little-endian FLOAT32 bytes** of exactly `DIM` length. Three independent ways to get silent-wrong or hard-error results:
- Writing `float64` bytes (numpy default is `float64`) into a `TYPE FLOAT32 DIM N` field → the byte length is 2× expected; RediSearch rejects it or, worse, misinterprets it.
- Endianness mismatch — a vector serialized big-endian (or via a non-`<f4` numpy view) produces garbage distances with **no error** (rankings silently wrong).
- Query vector dimensionality ≠ index `DIM` → `FT.SEARCH` errors (`Error parsing vector similarity query` / dimension mismatch). A model swap (e.g. 384-dim MiniLM → 1536-dim OpenAI) that isn't reflected in the field annotation `DIM` breaks every query.

**Why it happens:**
`np.array(vec).tobytes()` uses the platform/default dtype (`float64`) and native byte order. It "works" in a quick REPL on a little-endian x86/ARM box, so the bug hides until a cross-dtype or the wrong-model case appears. redisvl vectorizers return Python lists of floats, not bytes — the byte conversion is *rapyer's* responsibility and is the single most error-prone line in the feature.

**How to avoid:**
- Centralize FLOAT32 packing in **one** helper: `np.asarray(vec, dtype=np.float32).tobytes()` (numpy `float32` is IEEE-754 little-endian on all supported platforms; being explicit with `dtype=np.float32` fixes both dtype and width). Never let call sites hand-roll `.tobytes()`.
- Validate `len(vec) == field.dim` before packing, and assert `len(blob) == dim * 4`; raise a `RapyerError` subclass (fail-fast) rather than letting Redis emit a cryptic parse error.
- Make `DIM` a required field-annotation parameter (it is index-time schema per the design note) and cross-check it against the vectorizer's declared output dim at `init_rapyer()` — mismatch = raise, not warn.

**Warning signs:**
KNN returns results but rankings look random; `wrong number of arguments`/`Invalid vector length` from `FT.SEARCH`; blob length not divisible by 4; results differ between machines.

**Phase to address:** A (SF store + serialization) for packing/validation; C (index lifecycle) for dim/model cross-check at init.

---

### Pitfall 2: Distance-metric confusion (cosine vs L2 vs IP) and the normalization assumption

**What goes wrong:**
- Choosing `IP` (inner product) or `L2` while assuming cosine semantics. With **IP**, unnormalized vectors make magnitude dominate direction — longer texts win regardless of relevance. Cosine is magnitude-invariant; IP and L2 are not.
- Assuming Redis normalizes vectors. **It does not.** For `IP` to behave like cosine you must L2-normalize both stored and query vectors yourself. For `COSINE`, Redis handles normalization internally, so double-normalizing is harmless but pointless; for `IP` it is mandatory.
- Interpreting the returned distance/score wrong: for `COSINE`, Redis returns a **distance** in `[0,2]` (0 = identical), not a similarity in `[0,1]`. A `.near()` threshold coded as "score > 0.8 means similar" is inverted.

**Why it happens:**
Every embedding tutorial uses cosine; developers copy `IP` from a performance blog (IP is cheaper) without re-normalizing, or expose a "similarity ≥ threshold" API while Redis hands back a distance.

**How to avoid:**
- Default the field's `distance_metric` to **COSINE** — it is the safe, model-agnostic default and needs no client-side normalization. Document that IP requires caller-normalized vectors.
- Convert distance↔similarity in exactly one place in the `.near()` result-mapping layer (`similarity = 1 - cosine_distance/2` or the metric-appropriate transform), and expose *one* consistent semantic (recommend: similarity, higher = closer) to users.
- If IP is offered, normalize in the same central FLOAT32 helper (Pitfall 1) and refuse mixed normalized/unnormalized writes.

**Warning signs:**
Long documents always rank first (IP + unnormalized); threshold filters return the opposite of expected; scores outside the range the API claims.

**Phase to address:** A (metric declared at field annotation, normalization in the packing helper); D (distance→similarity mapping in `.near()`).

---

### Pitfall 3: SF HASH vector + co-located filter fields drift out of sync with the parent JSON doc

**What goes wrong:**
The design co-locates filterable fields into the SF HASH so one `FT.SEARCH` does atomic KNN+prefilter (option A). This **denormalizes** parent-doc fields into the SF key. When the parent doc's filter field changes via a normal `aupdate`/`__setattr__` that does not know about the RedisText SF, the copy in the HASH goes stale → hybrid queries filter on old values and return wrong parents. The vector itself drifts too: if the text changes but the embedding recompute/rewrite isn't wired into the same save, the HASH holds a vector for old text.

**Why it happens:**
rapyer's SF machinery already has a documented history of **nested special fields being silently dropped** (CONCERNS.md, fixed in 1.3.3) because actions iterated only top-level fields. Any denormalized copy needs every mutation path (`asave`, `aupdate`, `ainsert`, `aduplicate`, nested-field `__setattr__`) to re-project into the HASH, and it's easy to wire one path and miss the others. This is exactly the `_iter_special_fields` / `resolve_root_model` recursion trap called out for cascade.

**How to avoid:**
- Route every write that touches a co-located filter field or the text through the **same recursive SF save dispatch** (`_iter_special_fields`, `queue_special_loads_in_pipeline`) — never re-project in a hand-rolled path.
- Prefer **option B (FT.SEARCH-inside-Lua reading the parent doc)** for filters that are cheap to read fresh, and reserve co-location (A) for a small, explicitly-declared set of filter fields, minimizing the denormalized surface.
- Make text→vector recompute part of the atomic SF save: if `.text` is dirty, the new vector is computed client-side *before* the pipeline opens and both land in one MULTI/EXEC (see Pitfall 6).
- Add a regression test that mutates a co-located parent field through *each* mutation entry point and asserts the HASH copy updated.

**Warning signs:**
Hybrid KNN+filter returns models whose current field value contradicts the filter; search hits for text that was edited; failures only on nested-model RedisText fields.

**Phase to address:** A (SF save wiring through recursive helpers); D (hybrid query correctness tests across mutation paths).

---

### Pitfall 4: EmbeddingsCache keyed on `(content, model_name)` returns stale/wrong-dim vectors on model change

**What goes wrong:**
redisvl `EmbeddingsCache` hashes `(text, model_name)` → `{text, embedding, metadata}`. If you upgrade the underlying model but keep the same `model_name` string (e.g. a provider silently ships `text-embedding-3-small` v2, or you re-point a local `"minilm"` alias at a different checkpoint), the cache returns the **old** embedding — and if the new model has a different output dim, that cached vector now mismatches the index `DIM` (→ Pitfall 1) or, worse, is the right length but semantically from a different space (silently wrong rankings). The cache has no automatic invalidation on model change (verified: only `drop`/`drop_by_key` + optional TTL).

**Why it happens:**
`model_name` is a human label, not a content hash of the model weights/version. Cache correctness silently depends on the discipline of bumping that label on every model change.

**How to avoid:**
- Make the cache key incorporate a **version-bearing model identity**: use `f"{model_name}@{model_version_or_dim}"` (or include output dim + provider revision) so any change that could alter the vector produces a new key. Bake this into the adapter, not left to users.
- Treat `dim` as part of cache identity — a cached entry whose length ≠ current field `dim` must be ignored/dropped, not returned.
- Wire cache TTL conservatively and document that changing the embedding model requires a cache flush + index rebuild (they go together — Pitfall 5/7).

**Warning signs:**
Rankings degrade after a "no-op" dependency bump; dimension-mismatch errors appear only for previously-seen texts (cache hits) but not new ones (cache misses recompute correctly); identical text embeds differently across environments.

**Phase to address:** B (embedding adapter + cache key design).

---

### Pitfall 5: FLAT vs HNSW chosen without accounting for rebuild cost, recall, and memory

**What goes wrong:**
- Picking **HNSW** by default for a small dataset: HNSW carries per-vector graph overhead (`M` links/node) → materially higher memory and slower single-vector inserts than FLAT, with approximate recall you don't need under ~10–50k vectors.
- Picking **FLAT** for a large corpus: brute-force scan is exact but O(N) per query → latency grows linearly; fine at 10k, painful at 1M.
- Changing any index-time param (`algorithm`, `DIM`, `distance_metric`, HNSW `M`/`EF_CONSTRUCTION`) requires **dropping and rebuilding** the index and re-indexing every vector — there is no in-place alter. On a large keyspace this is a long, memory-heavy `FT.DROPINDEX` + `FT.CREATE` + backfill.

**Why it happens:**
Index params are annotation-level schema (design note). Developers pick HNSW because "it's the fast one" without the recall/memory tradeoff, then discover mid-milestone that tuning `M`/`EF` means a full rebuild.

**How to avoid:**
- Default to **FLAT** for the first cut (exact, simplest, no tuning) and make algorithm + HNSW params explicit annotation fields with documented tradeoffs; recommend HNSW only when the SF-key count is large.
- Treat the VECTOR index like a migration: `init_rapyer()` must detect a schema/param change and **drop+recreate+backfill** deliberately (Pitfall 7), and this must be a conscious, logged operation, not a silent surprise.
- Budget memory: ~`dim * 4 bytes` per vector for FLAT plus HNSW graph overhead; document the multiplier so users can size Redis (Pitfall 9).

**Warning signs:**
Query latency scales with corpus size (FLAT too big); Redis memory climbs faster than raw vector bytes (HNSW overhead); every param tweak forces a full re-embed.

**Phase to address:** C (index lifecycle + param declaration); documented sizing in D.

---

### Pitfall 6: Client-side embedding step breaks the atomicity story if sequenced wrong

**What goes wrong:**
Embedding is computed **client-side** (local HF model or remote API) and cannot be server-side atomic (design decision 5/8). The failure mode is sequencing the compute *inside* the pipeline/transaction window: opening the MULTI/pipeline, then awaiting a slow/remote vectorizer, then queuing the write. That holds a transaction (or a lock) open across a network call to a third-party API — long-held locks, connection starvation, and a partial-write window if the vectorizer throws after other commands are queued. The inverse mistake is doing text-write and vector-write as **two** client round-trips (TOCTOU: another writer interleaves).

**Why it happens:**
It's natural to write `async with apipeline(): vec = await vectorizer(text); ...`. The atomicity requirement is about the *write*, but the compute accidentally gets pulled inside the atomic boundary.

**How to avoid:**
- **Compute-then-commit**: resolve the vector (cache hit or vectorizer call) *entirely before* opening the pipeline; the atomic unit is only `text + vector → SF HASH + parent ref` in one MULTI/EXEC (or one SF-save `EVALSHA`). Vector is an already-materialized bytes blob by the time any Redis command is queued.
- Never `await` the vectorizer while holding `ensure_pipeline`/`alock`. Enforce with a code-review checklist item and, if feasible, an assertion that no vectorizer call occurs inside an active pipeline context.
- Handle vectorizer failure before any write is queued so a compute error aborts the save cleanly with nothing partially written.

**Warning signs:**
Lock-timeout errors under load; Redis "MULTI without EXEC"/aborted-transaction warnings; latency spikes correlated with embedding-API latency; occasional SF key present with parent ref absent (or vice versa).

**Phase to address:** A/B boundary (save sequencing); the save-path spike (001) already validated atomic save — verification here is sequencing discipline.

---

### Pitfall 7: VECTOR index lifecycle in `init_rapyer()` — recreate/drop, prefix collisions, DIALECT

**What goes wrong:**
- **Prefix/name collision:** the existing per-model indexes are `idx:{ClassName}` over the `{ClassName}:` prefix. The new VECTOR index is over the **SF-key prefix** `__rapyer_special__:...` — a genuinely different shape. Reusing the `idx:{ClassName}` name, or creating the vector index over the parent prefix, collides with the existing JSON index (RediSearch errors `Index already exists`, or worse indexes the wrong keys).
- **Stale schema on restart:** `init_rapyer()` recreates indexes; if it does `FT.CREATE` without reconciling an existing index whose params differ (dim/metric/algorithm changed — Pitfall 5), you either get `Index already exists` (no-op, silently keeps old schema) or must drop first. Dropping the wrong index nukes the JSON index.
- **Missing DIALECT 2:** KNN query syntax (`*=>[KNN k @vec $blob AS score]`) **requires `DIALECT 2`** (verified). Omitting it → parse error at query time, not index time, so it passes index creation and fails only on first search.
- **HASH vs JSON index type:** the vector index is over HASH SF keys (`ON HASH`), while existing indexes are `ON JSON`. Mixing the wrong `ON` type / attribute path (`$.vec` JSONPath vs plain `vec` HASH field) is a classic silent-empty-index bug.

**Why it happens:**
`init_rapyer()` already owns index creation for JSON indexes; the new index is a different `ON` type, different prefix, different name-space, and a different dialect requirement — several parallel schemas that are easy to conflate in one creation loop.

**How to avoid:**
- Give the vector index a **distinct name** (e.g. `idx:vec:{ClassName}:{field}` or a single `idx:__rapyer_text__`) over the `__rapyer_special__:` prefix, `ON HASH`, never reusing `idx:{ClassName}`.
- Set `DIALECT 2` on every KNN `FT.SEARCH` (and the `.near()` query builder), not just docs — add a test that asserts the dialect is present.
- In `init_rapyer()`, reconcile: read existing index info (`FT.INFO`), compare schema; on drift, **`FT.DROPINDEX` (keep docs) + recreate + backfill**, logged. Never blindly `FT.CREATE` and swallow `Index already exists`.
- Keep vector-index creation in a separate code path from the JSON-index loop so a bug in one can't corrupt the other.

**Warning signs:**
`Index already exists`; empty KNN results despite populated HASH keys (wrong `ON`/prefix/path); KNN parse error only at first query (missing DIALECT); JSON `afind` breaks after adding RedisText (name collision dropped/overwrote the JSON index).

**Phase to address:** C (index lifecycle) — highest-risk phase; flag for a dedicated spike-style verification against real Redis.

---

### Pitfall 8: fakeredis cannot do VECTOR/KNN — test-strategy blind spots and CI/version-matrix gaps

**What goes wrong:**
fakeredis has no RediSearch VECTOR/KNN (unsupported by design). Following the existing dual strategy naively, developers write unit tests that pass under fakeredis and *believe* the vector path is covered — but the entire KNN/index/hybrid surface is **only** exercisable on real Redis Stack (:6370). Same class of divergence already bit this codebase: `JSON.GET` WRONGTYPE not emulated, `JSON.MGET` `[]` vs `None`, Redis Functions unimplemented (CONCERNS.md). Additional matrix risk: RediSearch **vector** support requires a recent enough RediSearch/Redis Stack; the CI matrix spans Redis 6.0–7.4 and older RediSearch versions may lack vector fields or DIALECT 2, so a green matrix cell can mean "module too old, test skipped" rather than "passed".

**Why it happens:**
The suite is fakeredis-first for speed; the "unsupported by design" boundary is a documented decision but easy to violate by writing a plausible-looking fakeredis test that silently exercises nothing (or a no-op fallback, exactly like the cascade `CascadeResult(0,0)` fakeredis no-op).

**How to avoid:**
- Split coverage explicitly: fakeredis unit tests cover **store/serialization/cache/adapter** only (FLOAT32 packing, cache keying, SF save queuing shape). KNN/index/hybrid live under `tests/integration/` gated on `real_redis_client`, mirroring the `requires_redis_functions` gate pattern already in the repo.
- Add a **`requires_vector_search`** pytest gate that probes RediSearch module version / attempts a tiny VECTOR `FT.CREATE` and **skips with a loud reason** if unavailable — so a skipped cell is visible, never a false green.
- Ensure CI's real-Redis service is a RediSearch version with vector + DIALECT 2 (Redis Stack, or pin a module version); document the minimum. Don't assume all 6.0–7.4 cells have vectors.
- Guard against the cascade-style trap: no fakeredis fallback that returns empty results for KNN — the vector path should raise a clear "requires real Redis" error under fakeredis, not silently return nothing.

**Warning signs:**
Vector features "fully tested" but coverage is all fakeredis; integration job passes on an old-module cell that actually skipped; KNN behavior differs between local (real) and CI.

**Phase to address:** E (test strategy / CI / matrix) — must be scoped alongside every other phase, not deferred.

---

### Pitfall 9: Optional-extra import guards — `ImportError` when redisvl absent

**What goes wrong:**
redisvl (and its heavy transitive deps: HF/torch/sentence-transformers) is an optional `rapyer[embeddings]` extra. Two failure modes:
- A top-level `import redisvl` in a module that's imported on **every** `import rapyer` → base installs (no extra) crash at import time, breaking the whole library for users who never touch RedisText.
- The `@init_subclass__` metaclass or `init_rapyer()` eagerly instantiates a vectorizer even for models with no RedisText field → import/instantiation cost + failure leaks into unrelated code paths.

**Why it happens:**
The codebase forbids in-function imports as a convention (MEMORY: "No in-function imports"), which pushes toward top-level imports — but optional extras are the *one* legitimate exception. Getting the guard wrong either violates the convention or breaks base installs.

**How to avoid:**
- Isolate all redisvl imports behind a **thin adapter module** that is imported lazily (module-level `try/except ImportError` setting a sentinel, or a guarded accessor). This is the sanctioned exception to the no-in-function-imports rule — document it in the adapter with a comment.
- Raise a **clear, actionable error** when a RedisText feature is used without the extra: `raise RapyerError("RedisText requires the 'embeddings' extra: pip install rapyer[embeddings]")` — a `RapyerError` subclass, not a raw `ImportError`.
- Never touch redisvl at `import rapyer` time or in `__init_subclass__` for models without a RedisText field; only when RedisText is actually declared/used and `init_rapyer()` wires a vectorizer.
- Test the base-install path in CI (a job without the extra) that imports rapyer and runs the non-vector suite — proves the guard.

**Warning signs:**
`ImportError: No module named 'redisvl'` on `import rapyer` in a lean install; torch pulled into a base install; CI has no "extra-absent" job.

**Phase to address:** B (adapter + extra packaging); E adds the extra-absent CI job.

---

### Pitfall 10: Large-text / token-limit and vector memory blowup

**What goes wrong:**
- Text exceeding the embedding model's token limit (e.g. 512 tokens for many local models, 8191 for OpenAI) is **silently truncated** by the vectorizer → the embedding represents only the head of the document; tail content is unsearchable, with no error.
- Storing many vectors blows Redis memory: each vector is `dim*4` bytes (1536-dim = ~6KB) *plus* HNSW graph overhead *plus* the co-located filter fields *plus* the cached copy in EmbeddingsCache — a corpus can consume multiples of the raw text size, and it's all in-RAM.

**Why it happens:**
Vectorizers truncate by default without raising; developers size Redis on text bytes, forgetting vectors + index + cache are separate, RAM-resident copies.

**How to avoid:**
- Surface the model's max-token limit in the adapter; either **raise/warn on truncation** or document chunking as out-of-scope so users know one RedisText = one vector for the (possibly truncated) whole text.
- Document memory sizing: total ≈ `N * (dim*4 + hnsw_overhead + filter_field_bytes)` + cache. Recommend TTL on the cache and (optionally) on the SF keys via the existing `Meta.ttl`/cascade machinery.
- Consider a configurable max-text-length guard at the field level to fail fast rather than silently truncate.

**Warning signs:**
Search misses content known to be in a long document; Redis `used_memory` far exceeds text corpus size; OOM under load with many RedisText models.

**Phase to address:** B (truncation handling in adapter); D/documentation (memory sizing); TTL reuse in C.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hand-roll `.tobytes()` at each call site | Fewer helpers, quick to write | dtype/endianness bugs scattered; impossible to fix in one place | Never — always one FLOAT32 helper |
| Co-locate *all* parent filter fields into SF HASH | Simple one-`FT.SEARCH` hybrid for any filter | Wide denormalization surface → staleness bugs across every mutation path | Only for a small, explicitly-declared filter set; prefer Lua-FT.SEARCH (B) otherwise |
| Cache keyed on bare `model_name` | Matches redisvl default | Silent stale/wrong-dim vectors on model change | Never — include model version + dim in key |
| `FT.CREATE` and swallow `Index already exists` | init idempotent-looking, no drop logic | Old schema silently retained after a param/dim change | Never for the vector index — reconcile via `FT.INFO` + drop/rebuild |
| fakeredis test that hits a no-op vector fallback | Green in fast unit lane | False coverage; real bugs ship (cascade `CascadeResult(0,0)` precedent) | Never — vector path must raise under fakeredis, gate real-Redis tests |
| Default to HNSW everywhere | "Fast" out of the box | Memory + insert overhead + tuning-requires-rebuild for small corpora | Only when SF-key count is genuinely large |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| RediSearch VECTOR index | Omitting `DIALECT 2` on KNN search; wrong `ON` type (JSON vs HASH) or wrong attribute path | Always `DIALECT 2`; `ON HASH` over `__rapyer_special__:` prefix; plain HASH field name for the vector |
| RediSearch index naming | Reusing `idx:{ClassName}` / parent prefix → collides with existing JSON index | Distinct vector-index name over the SF-key prefix; separate creation path in `init_rapyer()` |
| redisvl vectorizer | Awaiting compute inside the pipeline/lock; assuming vectors are pre-normalized | Compute-then-commit; normalize in the FLOAT32 helper if metric is IP |
| redisvl EmbeddingsCache | Bare `(text, model_name)` key; no invalidation on model swap; API drift (0.7→0.23, verified) | Version+dim in key; pin redisvl behind adapter; drop/rebuild cache+index together on model change |
| redisvl optional extra | Top-level import breaks base installs | Guarded adapter module; clear `RapyerError` when extra missing; extra-absent CI job |
| Redis Stack module version | Assuming all matrix cells have vector fields / DIALECT 2 | `requires_vector_search` probe-and-skip gate; pin minimum RediSearch version in CI |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| FLAT index on a large corpus | Query latency grows linearly with vector count | Use HNSW past ~50k vectors; document threshold | ~50k–100k vectors |
| Embedding recompute on every save (cold cache / bad key) | Save latency dominated by vectorizer; API cost | Correct cache key (Pitfall 4); cache hit for unchanged text | Any high-write workload |
| N+1 parent resolution after KNN | KNN returns k SF keys, then k separate `aget`s | Batch-resolve parents by class via `JSON.MGET` (reuse `execute_load_pipeline`); note existing N+1 FK debt in CONCERNS.md | k large / many queries |
| Vector memory blowup | `used_memory` >> text corpus | Size for `dim*4 + HNSW overhead + filters + cache`; TTL the cache | Large N, high dim (1536+) |
| Unbounded KNN + no result cap | Scanning/returning huge result sets | Require `k`; route enumeration through SCAN not KEYS (existing repo trap) | Large keyspace |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Sending text to a remote embedding API without disclosure | PII/confidential text leaves the trust boundary | Document that remote vectorizers transmit text; support local models; note in docs like the existing "Redis is a trusted store" guidance |
| Pickling embedding/adapter objects into fields | Unsafe `pickle.loads` on read (existing CONCERNS risk) | Store vectors as raw HASH bytes, not pickled Python objects; keep vectors out of the pickle path |
| Embedding-API key handling | Key in code/logs | Delegate to caller-supplied vectorizer config; never log the key or the request body |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Exposing raw Redis cosine *distance* as "similarity" | Threshold filters behave inverted; confusing scores | Map to one consistent similarity semantic (higher = closer) in `.near()` |
| `DIM`/metric/algorithm buried or defaulted invisibly | Silent model/dim mismatch; surprise rebuilds | Required, explicit annotation params; fail-fast validation at `init_rapyer()` |
| Silent truncation of long text | Users think full document is searchable | Warn/raise on truncation; document one-vector-per-field semantics |
| Accessing `.near()` results assuming eager parent hydration | Extra awaits / N+1 surprise | Document resolution model; offer batched parent resolve |

## "Looks Done But Isn't" Checklist

- [ ] **FLOAT32 packing:** Often missing explicit `dtype=np.float32` and length assertion — verify blob length == `dim*4` and cross-machine determinism.
- [ ] **KNN query:** Often missing `DIALECT 2` — verify every `.near()`/global-search query sets it (test asserts it).
- [ ] **Index lifecycle:** Often missing schema reconciliation — verify `init_rapyer()` detects dim/metric/algorithm drift and drops+rebuilds+backfills (not silent `Index already exists`).
- [ ] **Co-located filters:** Often missing re-projection on some mutation path — verify HASH copy updates via `asave`, `aupdate`, `ainsert`, `aduplicate`, and nested `__setattr__`.
- [ ] **Cache key:** Often missing model version/dim — verify a model swap yields new keys and never returns wrong-dim vectors.
- [ ] **Optional extra:** Often missing base-install guard — verify `import rapyer` works with no `embeddings` extra and a clear error on RedisText use.
- [ ] **Atomicity:** Often missing sequencing check — verify vectorizer is never awaited inside an open pipeline/lock; text+vector land in one MULTI/EXEC.
- [ ] **fakeredis path:** Often a silent no-op — verify the vector path raises "requires real Redis" under fakeredis rather than returning empty.
- [ ] **Version matrix:** Often a false-green skip — verify `requires_vector_search` skips loudly and CI's real Redis has vectors + DIALECT 2.
- [ ] **Distance semantics:** Often missing normalization for IP — verify metric choice and normalization match, and score mapping is right-way-round.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong index schema (dim/metric/algorithm) shipped | MEDIUM | `FT.DROPINDEX` (keep docs), `FT.CREATE` with correct schema, backfill: re-pack all vectors from stored text (recompute if dim changed) |
| Stale cache after model change | LOW | Flush EmbeddingsCache (namespace/keyspace), bump model-version in key, re-embed on next access |
| Denormalized HASH filter fields drifted | MEDIUM | Backfill job re-projecting parent fields into SF HASHes; add the missing mutation-path wiring + regression test |
| Endianness/dtype corruption in stored vectors | HIGH | All stored vectors invalid → full re-embed/backfill from source text; fix the central packing helper first |
| Base install broken by top-level redisvl import | LOW | Move import behind guarded adapter; add extra-absent CI job; patch release |
| FLAT too slow at scale | MEDIUM | Recreate index as HNSW with tuned `M`/`EF`, backfill (no re-embed needed — same vectors) |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. FLOAT32 encoding/dim | A (serialization) + C (init cross-check) | Blob length + cross-machine test; init raises on dim mismatch |
| 2. Distance metric / normalization | A (metric decl) + D (score mapping) | Metric-specific ranking tests; score-range assertion |
| 3. SF/co-located field staleness | A (recursive SF save) + D (hybrid tests) | Mutate via every entry point, assert HASH updated |
| 4. Cache key stale on model change | B (adapter cache key) | Model-swap test yields new keys, no wrong-dim returns |
| 5. FLAT vs HNSW / rebuild cost | C (index params + migration) | Param-change triggers logged drop/rebuild; memory sizing doc |
| 6. Client-embed atomicity sequencing | A/B (save path) | No vectorizer await inside pipeline (assert); atomic write test |
| 7. Index lifecycle / prefix / DIALECT | C (init lifecycle) — flag for spike-level rigor | Distinct name, `ON HASH`, DIALECT 2 asserted; JSON index intact after adding RedisText |
| 8. fakeredis untestable / matrix | E (test strategy) — cross-cutting | `requires_vector_search` skips loudly; real-Redis integration gate; extra-absent + module-version CI |
| 9. Optional-extra import guard | B (adapter/packaging) + E (CI job) | `import rapyer` clean with no extra; clear error on use |
| 10. Token limit / memory blowup | B (truncation) + D/docs (sizing) | Truncation warns/raises; memory formula documented |

## Sources

- [Redis vector search concepts (FLAT/HNSW, COSINE/L2/IP, FLOAT32, DIM)](https://redis.io/docs/latest/develop/ai/search-and-query/vectors/) — HIGH
- [Redis vector KNN tutorial (KNN syntax, DIALECT 2)](https://redis.io/tutorials/howtos/solutions/vector/getting-started-vector/) — HIGH
- [redis-py vector similarity examples (blob PARAMS, DIALECT 2)](https://redis.readthedocs.io/en/stable/examples/search_vector_similarity_examples.html) — HIGH
- [RedisVL EmbeddingsCache API (set/get/drop, keyed on content+model, TTL)](https://docs.redisvl.com/en/stable/api/cache.html) — HIGH
- [RedisVL Caching Embeddings user guide](https://docs.redisvl.com/en/latest/user_guide/10_embeddings_cache.html) — HIGH
- [Redis vector index tips (HNSW memory/recall tradeoffs)](https://medium.com/@Modexa/8-redis-vector-index-tips-for-low-latency-retrieval-585aeb3b69b6) — MEDIUM
- `.planning/codebase/CONCERNS.md` — fakeredis/real-Redis divergence history, nested-SF drop bugs, N+1 FK, Redis Functions fakeredis gap — HIGH (repo-internal)
- `.planning/notes/redistext-design-decisions.md`, `.planning/spikes/MANIFEST.md` — locked decisions + validated spikes — HIGH (repo-internal)

---
*Pitfalls research for: adding RedisText (text + embeddings + RediSearch VECTOR/KNN) to the rapyer Redis ORM*
*Researched: 2026-07-20*
