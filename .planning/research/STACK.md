# Stack Research

**Domain:** Text embeddings + RediSearch VECTOR/KNN for a new `RedisText` special field type in the `rapyer` Redis ORM (subsequent milestone — only the NEW embeddings/vector-search additions are in scope)
**Researched:** 2026-07-20
**Confidence:** HIGH (versions and dep graph verified against PyPI JSON API + redisvl `main` source on 2026-07-20; async-fallback behavior read directly from redisvl source)

## Scope Note

Everything rapyer already ships — pydantic v2 models as RedisJSON, ForeignKey, transactional pipelines (MULTI/EXEC), Lua/`EVALSHA` with SHA registration + `NoScriptError` self-heal, SF types under `__rapyer_special__:` keys, RediSearch JSON indexing, redis-py asyncio (7.0.1), Redis Stack on :6370, uv + tox, Python 3.10–3.13 — is a validated given and is **not** re-litigated here. This file covers only what the RedisText milestone *adds*: an embedding-compute/cache layer and a VECTOR/KNN index layer.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `redisvl` | `==0.23.0` (pin exact) | Text→vector via pluggable vectorizers + `EmbeddingsCache` (exact-text dedup). Shipped as the optional `rapyer[embeddings]` extra, wrapped behind a thin rapyer adapter. | Team decision. Official Redis library; gives vectorizer abstraction + a working async cache without hand-rolling provider SDKs. Latest is 0.23.0 (verified). **Pin exactly** — the `text`→`content` kwarg drift between 0.7 and 0.23 (spike 003) proves the API is unstable across minors; the adapter is the only place that touches redisvl. |
| Redis Stack (RediSearch `VECTOR`) | RediSearch 2.10 (already deployed :6370) | KNN index over the SF-key HASH prefix (`*=>[KNN k @field $blob AS dist]`, DIALECT 2, `PARAMS 2 blob <float32-bytes>`). | Already validated in spike 001/002 — no new server component. rapyer builds this `FT.CREATE ... ON HASH PREFIX __rapyer_special__:...` itself (new index shape, distinct from `idx:{ClassName}` JSON indexes). |
| `redis-py` (asyncio) | `7.0.1` (unchanged) | The wire client for both the VECTOR index and the EmbeddingsCache. redisvl uses redis-py underneath; rapyer's own SF save/KNN path uses `redis.asyncio` directly. | No bump needed — redisvl 0.23.0 requires `redis<8.0,>=5.0`; rapyer's pinned 7.0.1 sits inside that range. Reuse rapyer's existing client, don't let redisvl open its own. |

### Supporting Libraries

These arrive **transitively** with `redisvl` core (the `rapyer[embeddings]` base extra). Do not add them to rapyer's own dependency list.

| Library | Version (resolved by redisvl 0.23.0) | Purpose | When to Use |
|---------|--------------------------------------|---------|-------------|
| `numpy` | `>=1.26.0,<3` | float list ↔ FLOAT32 little-endian blob (`redisvl.redis.utils.array_to_buffer`) — exactly the blob format spike 001 used for HASH storage + KNN `PARAMS`. | Always (when the extra is installed). Heaviest core dep. |
| `ml-dtypes` | `>=0.4.0,<1.0.0` | numpy support for `float16`/`bfloat16` vector dtypes. | Only matters if a field opts into non-FLOAT32; design defaults to FLOAT32 so this is dormant weight. |
| `jsonpath-ng`, `python-ulid`, `pyyaml`, `tenacity`, `pydantic` | see below | redisvl internals (schema, retries, ids). `pydantic<3,>=2` overlaps rapyer's 2.11–2.13. | Transitive; no action. |

Base `redisvl` install = ~13 packages, no torch (confirmed spike 003 + dep graph). Lean by design.

### Vectorizer Providers (SECOND, deeper opt-in — NOT in the base extra)

`redisvl` exposes vectorizers as its own extras; the heavy ML deps live behind them. Verified from redisvl 0.23.0 `requires_dist`:

| redisvl extra | Pulls | Weight | Async story |
|---------------|-------|--------|-------------|
| `sentence-transformers` (`HFTextVectorizer`) | `sentence-transformers>=3.4.0,<4` → **torch** | HEAVY (hundreds of MB, GPU/CPU-bound) | **Sync only.** `aembed` logs a warning and falls back to blocking `_embed` (`self._client.encode(...)`) — runs on the event loop. |
| `openai` (`OpenAITextVectorizer`) | `openai>=1.1.0` (httpx) | LIGHT | True async `_aembed` via provider async client. |
| `cohere` | `cohere>=4.44` | LIGHT | Provider async client. |
| `vertexai` | `google-cloud-aiplatform`, `protobuf` | MEDIUM | Provider client. |
| `bedrock` | `boto3` | MEDIUM | boto3. |
| `mistralai` / `ollama` / `voyageai` | resp. SDK | LIGHT–MEDIUM | Provider clients. |
| `custom` (`CustomTextVectorizer`) | none | ZERO | User supplies the embed callable. |

**Recommendation:** `rapyer[embeddings]` = `redisvl` **only** (no provider deps). Do **not** fold torch/sentence-transformers into it. Let users layer the provider they want. Offer thin passthrough sub-extras for the two most likely paths:
- `rapyer[embeddings-hf]` → `redisvl[sentence-transformers]` (local, offline, no API key)
- `rapyer[embeddings-openai]` → `redisvl[openai]` (API, lean, no torch)

and document "bring-your-own" via `CustomTextVectorizer` for everything else. This keeps `pip install rapyer` and even `pip install rapyer[embeddings]` free of torch.

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` extras | Declare `[project.optional-dependencies] embeddings = ["redisvl==0.23.0"]` + the sub-extras above. | Keep redisvl out of the default `dev`/test groups; add a dedicated `embeddings` test path that installs it, mirroring spike 003's `uv run --with redisvl`. |
| tox env | A vector/embeddings integration env, real-Redis-only. | fakeredis is unsupported for the VECTOR/KNN path **by design** (locked decision). Gate these tests on real Redis (:6370); keep store/cache/serialization unit tests fakeredis-capable. |

## Installation

```bash
# rapyer base — unchanged, lean, NO redisvl / numpy / torch
uv sync

# Embeddings + KNN capability (adapter + redisvl core; still no torch)
uv pip install "rapyer[embeddings]"        # -> redisvl==0.23.0 (+ numpy, ml-dtypes, ...)

# Local Hugging Face vectorizer (pulls torch — heavy, opt-in)
uv pip install "rapyer[embeddings-hf]"     # -> redisvl[sentence-transformers]

# API-based vectorizer (lean, no torch)
uv pip install "rapyer[embeddings-openai]" # -> redisvl[openai]
```

## Async-Fit Strategy (the load-bearing integration decision)

rapyer is async-first; every I/O method is `a`-prefixed. redisvl's async surface is uneven and the adapter must normalize it:

1. **Cache layer is genuinely async.** `EmbeddingsCache.aget/aset/amget/amset/aexists/adrop` run on `redis.asyncio` and round-trip cleanly on :6370 (spike 003). Use these directly.
2. **Local (HF) vectorizers are NOT async.** `HFTextVectorizer.aembed` falls back to synchronous `SentenceTransformer.encode`, which blocks the event loop (verified in redisvl `base.py` `_aembed`). The adapter **must** offload local/CPU-bound embeds with `asyncio.to_thread(vectorizer.embed, content)` (or a bounded executor) so a single embed call can't stall the whole async app. Do not call `aembed` and assume non-blocking.
3. **API vectorizers ARE async.** OpenAI/Cohere/etc. implement real `_aembed` over async HTTP — call `aembed` directly, no thread offload.
4. **Adapter picks the path.** Expose one `async def aembed(content) -> list[float]` on the adapter that: (a) checks whether the wrapped vectorizer implements a real `_aembed` vs the base fallback and routes to `to_thread` accordingly, or (b) simply always `to_thread`s local vectorizer types and awaits provider vectorizers. Keep this decision inside the adapter — the rest of rapyer only ever `await`s the adapter.
5. **Cache wiring is free.** `BaseVectorizer` accepts a `cache=EmbeddingsCache(...)` arg and does cache-lookup-then-embed internally (sync `embed` and async `aembed` both honor it). The adapter can pass rapyer's configured `EmbeddingsCache` in at construction and get dedup for free — but note the cache lookup inside the sync `embed` is itself sync, so the `to_thread` offload for local vectorizers also covers the (blocking) cache read; for provider vectorizers the internal cache read uses `aget`. Decide whether rapyer owns cache reads explicitly (clearer TTL alignment) vs. delegating to the vectorizer.

## Vector Index Params as Field-Annotation Schema

Locked design: dim/metric/algorithm/type are index-time schema declared on the field (mirroring `Index[...]`). Map annotation params straight onto RediSearch `VECTOR` field attributes. redisvl's own enums (from `redisvl/schema/fields.py`) are the authoritative value set to validate against:

| rapyer field-annotation param | RediSearch attr | Allowed values (redisvl enums) | Default |
|-------------------------------|-----------------|--------------------------------|---------|
| `dim` | `DIM` | positive int, **must equal the vectorizer's `dims`** | none (required; validate at `init_rapyer()` against the wired vectorizer) |
| `metric` | `DISTANCE_METRIC` | `COSINE`, `L2`, `IP` | `COSINE` |
| `algorithm` | index algo | `FLAT`, `HNSW` (+ HNSW `M`/`EF_CONSTRUCTION`/`EF_RUNTIME`) | `FLAT` (simple, exact; HNSW for large corpora) |
| `dtype` | `TYPE` | `FLOAT32` (design default), also `FLOAT16`/`FLOAT64`/`BFLOAT16` | `FLOAT32` |

Wire the **vectorizer instance + Redis connection at `init_rapyer()`** (like `Meta.redis`); pull **per-field vector params from the annotation**. Build the `FT.CREATE ... ON HASH PREFIX __rapyer_special__:...` yourself (rapyer already owns FT.CREATE for JSON indexes) — you can reuse redisvl's `VectorDataType`/`VectorDistanceMetric`/`VectorIndexAlgorithm` enums for validation without adopting redisvl's IndexSchema/index-management machinery. Validate `dim == vectorizer.dims` at init and fail fast (same fail-fast posture as the cascade `Meta.ttl` check).

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| redisvl (team decision) | Call provider SDKs (openai/sentence-transformers) directly, no redisvl | If redisvl's cross-minor API churn becomes worse than the value of its cache — but you'd then reimplement `EmbeddingsCache` (content-hash keyspace, TTL, async round-trip). Not worth it now; the adapter already isolates the churn. |
| redisvl `EmbeddingsCache` as the dedup layer | rapyer-native embedding cache in its own keyspace | If you need the cache TTL tightly coupled to rapyer's cascade-TTL semantics. `EmbeddingsCache` supports per-entry TTL (spike 003), so start with it; revisit only if cascade alignment demands it. It is a *third, independent* keyspace (`{name}:{sha256(content)}`), separate from the SF key and parent doc — it is recompute-avoidance, never the source of truth for a field's vector. |
| HASH storage for the SF value | JSON storage | Spike 001: HASH and JSON give identical KNN distances. HASH is leaner and the classic vector pattern; use JSON only if human-readable SF values are a hard requirement. |
| `rapyer[embeddings]` = redisvl only | Bundle sentence-transformers into the extra | Never for the default extra — it drags torch into every embeddings user. Only via the explicit `embeddings-hf` sub-extra. |

## What NOT to Use / NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| torch / sentence-transformers in the base or `[embeddings]` extra | Hundreds of MB; violates the lean-base constraint; irrelevant to API-vectorizer users | Behind `rapyer[embeddings-hf]` only |
| `redisvl>=0.23` or `~=0.23` (range pins) | The `content`/`text` drift proves minors break the API; a range lets an install silently move to a broken signature | `redisvl==0.23.0` exact, re-validated by the adapter's own tests on any bump |
| redisvl's `SearchIndex`/`AsyncSearchIndex` index-management + query builders | Duplicates rapyer's existing FT.CREATE/FT.SEARCH ownership and its atomicity model; would fork index lifecycle out of `init_rapyer()` | rapyer's own index creation over the SF prefix; reuse only redisvl's *vectorizers*, *EmbeddingsCache*, and *enum/blob helpers* (`array_to_buffer`) |
| redisvl opening its own Redis connection | Two client pools, TTL/pipeline machinery bypassed | Pass rapyer's configured `redis.asyncio` client / URL into redisvl objects |
| Calling `vectorizer.aembed` and assuming it doesn't block (local models) | HF `aembed` is a sync fallback that blocks the event loop | `asyncio.to_thread` in the adapter for local/CPU-bound vectorizers |
| fakeredis for the VECTOR/KNN path | Cannot do RediSearch VECTOR/KNN (locked design decision) | Real Redis Stack :6370 integration tests; fakeredis only for store/cache/serialization units |

## Stack Patterns by Variant

**If the user wants offline / no-API-key embeddings:**
- `rapyer[embeddings-hf]` → `HFTextVectorizer` (sentence-transformers/torch)
- Adapter routes embeds through `asyncio.to_thread` (blocking model inference)
- Default model `sentence-transformers/all-mpnet-base-v2` → `dim=768`

**If the user wants lean, hosted embeddings:**
- `rapyer[embeddings-openai]` → `OpenAITextVectorizer` (httpx, real async, no torch)
- Adapter awaits `aembed` directly
- `text-embedding-3-small` → `dim=1536` (declare on the field annotation)

**If the user has their own embedding function:**
- `rapyer[embeddings]` only → `CustomTextVectorizer`
- Zero extra deps; user supplies the callable; adapter still owns thread-offload policy

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `redisvl==0.23.0` | `redis 7.0.1` (rapyer's pin) | redisvl requires `redis<8.0,>=5.0` — 7.0.1 is inside the range. Verified. |
| `redisvl==0.23.0` | `pydantic 2.11–2.13` (rapyer's range) | redisvl requires `pydantic<3,>=2`. Overlaps fully. (Note: redisvl's HF vectorizer imports `pydantic.v1.PrivateAttr` internally — works under v2's compat shim, no action needed.) |
| `redisvl==0.23.0` | Python 3.10–3.13 (rapyer's range) | redisvl requires `<3.15,>=3.10`. Full overlap. Verified. |
| `redisvl==0.23.0` | RediSearch 2.10 (:6370) | Vector index + KNN DIALECT 2 already proven on this server (spikes 001/002). |
| `numpy<3,>=1.26.0` | Python 3.10–3.13 | uv/pip resolves the right numpy per interpreter (numpy 2.5+ needs py≥3.12; older numpy covers 3.10–3.11). No manual pin needed. |
| `redisvl[sentence-transformers]` | — | Pins `sentence-transformers>=3.4.0,<4` (latest is 5.6.0, held back by redisvl's cap). Acceptable; opt-in only. |

## Sources

- PyPI JSON API `pypi.org/pypi/redisvl/json` — latest **0.23.0**, `requires_python <3.15,>=3.10`, full `requires_dist` (core + every provider extra). HIGH.
- `github.com/redis/redis-vl-python` (`main`) `redisvl/utils/vectorize/base.py` — `aembed`/`_aembed` sync-fallback-with-warning for local vectorizers; `content`/`text` deprecated-arg; built-in `cache=` param. HIGH.
- `.../vectorize/text/huggingface.py` — `HFTextVectorizer` uses blocking `SentenceTransformer.encode`, no real async. HIGH.
- `.../schema/fields.py` — `VectorDataType` (`float16/float32/float64/bfloat16`), `VectorDistanceMetric` (`COSINE/L2/IP`), `VectorIndexAlgorithm` (`FLAT/HNSW`) enums. HIGH.
- PyPI current versions: sentence-transformers 5.6.0, openai 2.46.0, cohere 7.0.6, torch 2.13.0, numpy 2.5.1. HIGH.
- rapyer spikes 001 (VECTOR/KNN over SF HASH prefix, atomic save), 003 (EmbeddingsCache async round-trip, 0.7→0.23 API drift, ~13-package lean core). VALIDATED. HIGH.

---
*Stack research for: text-embeddings + RediSearch VECTOR/KNN additions to the rapyer Redis ORM (RedisText milestone)*
*Researched: 2026-07-20*
