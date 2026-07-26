# Project Research Summary

**Project:** rapyer — RedisText (text + vector embeddings, KNN semantic search) — milestone v1.3.6
**Domain:** Semantic/vector search (text + embeddings, RediSearch VECTOR/KNN) added as a new Special Field type to an existing async Redis ORM
**Researched:** 2026-07-20
**Confidence:** HIGH (three feasibility spikes already VALIDATED; stack/versions verified against PyPI + redisvl source; only lifecycle/ergonomics judgment calls sit at MEDIUM)

## Executive Summary

RedisText is a new `SpecialFieldType` that stores one text value plus its FLOAT32 vector embedding under its own Redis HASH key (`__rapyer_special__:...`), referenced from the parent JSON doc — exactly the SF pattern `RedisSet`/`RedisPriorityQueue` already use. On top of that store sits a RediSearch `VECTOR` index built over the SF-key prefix, queried via a `.near('text', k=...)` node that composes into `afind(...)` with `& | ~`, plus a top-level global similarity method. Embeddings are produced client-side by a redisvl vectorizer (wrapped in a thin, version-pinned adapter shipped behind the optional `rapyer[embeddings]` extra) with a redisvl `EmbeddingsCache` fronting it to avoid recompute. Three spikes have already de-risked the load-bearing questions: KNN over an SF HASH prefix with atomic combined save (spike 001), co-located-TAG hybrid prefilter + `FT.SEARCH`-callable-inside-Lua (spike 002), and async `EmbeddingsCache` round-trip + redisvl 0.7→0.23 API drift (spike 003).

The recommended approach follows a strict **adapter → type/save → index → query** build order. The embedding adapter is the leaf dependency and the only place that touches redisvl (containing its cross-minor API churn — pin `redisvl==0.23.0` exactly); the save path defines the SF-key/HASH shape; the index must exist before any KNN query runs; the query surface (default = co-located-TAG atomic hybrid, spike 002 Approach A) comes last. The Lua `FT.SEARCH` fallback (Approach B, for prefiltering on non-denormalized parent fields) is a deferrable escape hatch — the co-located-TAG default satisfies the atomic-hybrid requirement on its own. Steps 1–2 are the only fakeredis-testable slices; everything vector/KNN is real-Redis-only (:6370) **by design** — this is a locked decision, not a gap.

The dominant risks are all correctness-silent-until-production: FLOAT32 dtype/endianness/dim mismatch (centralize packing in one `np.asarray(vec, dtype=np.float32).tobytes()` helper with length assertions), distance-metric confusion (default COSINE, map distance→similarity in exactly one place), co-located-TAG drift when a parent field changes through a mutation path that doesn't re-project into the SF HASH, EmbeddingsCache returning a stale/wrong-dim vector when the model changes under a reused `model_name` (bake model-version+dim into the cache key), the VECTOR index colliding with the existing `idx:{ClassName}` JSON index (distinct name + tightly-scoped prefix + `FT.INFO` reconciliation), and breaking base installs with a top-level `import redisvl` (guarded adapter, clear `RapyerError`, extra-absent CI job). The atomicity constraint has a specific sharp edge: **compute the vector entirely before opening the pipeline** — never `await` a vectorizer inside an open `ensure_pipeline`/`alock` window.

## Key Findings

### Recommended Stack

Only the NEW embedding/vector layer is in scope; all existing rapyer machinery (pydantic-v2-as-RedisJSON, SF dispatch, transactional pipelines, Lua/`EVALSHA` with SHA self-heal, RediSearch JSON indexing, redis-py 7.0.1 asyncio, uv/tox, Py 3.10–3.13) is a validated given. The additions are an embedding-compute/cache layer (redisvl) and a VECTOR/KNN index layer (RediSearch, already deployed). See [STACK.md](STACK.md).

**Core technologies:**
- `redisvl==0.23.0` (pinned exact) — text→vector vectorizers + `EmbeddingsCache`; shipped as the `rapyer[embeddings]` extra, touched only through a thin adapter. Exact pin because the `text`→`content` kwarg drift between minors (spike 003) proves the API is unstable.
- RediSearch VECTOR (RediSearch 2.10 on :6370, already deployed) — KNN index over the SF-key HASH prefix (`(*)=>[KNN k @field $blob AS dist]`, DIALECT 2, `PARAMS 2 blob <f32-bytes>`). No new server component; rapyer builds `FT.CREATE ... ON HASH PREFIX` itself.
- `redis-py` 7.0.1 (unchanged) — same client for the VECTOR path and the cache; sits inside redisvl's `redis<8.0,>=5.0` range. Reuse rapyer's client; never let redisvl open its own pool.
- `numpy>=1.26,<3` — arrives transitively with the extra; the FLOAT32 little-endian blob conversion. `rapyer[embeddings]` = **redisvl only, no torch**; providers layer via `rapyer[embeddings-hf]` (sentence-transformers/torch, sync-only → thread-offload) and `rapyer[embeddings-openai]` (lean, real async), plus bring-your-own `CustomTextVectorizer`.

**Load-bearing integration decision — async fit:** the adapter must normalize redisvl's uneven async surface. Cache ops are genuinely async (use directly). Local HF vectorizers' `aembed` is a *blocking* sync fallback — the adapter **must** `asyncio.to_thread(vectorizer.embed, ...)` for CPU-bound/local vectorizers; API vectorizers (OpenAI/Cohere) implement real `_aembed` and are awaited directly. The rest of rapyer only ever `await`s the adapter.

### Expected Features

See [FEATURES.md](FEATURES.md). rapyer's edge is the **ORM integration + atomicity guarantee**, not the vector search itself (that's RediSearch's).

**Must have (table stakes, all P1):**
- `RedisText` SF field: one text + one FLOAT32 vector under its own HASH key.
- Auto-embed on save via redisvl vectorizer + `EmbeddingsCache`; atomic text+vector write (one pipeline op).
- Annotation-level vector schema (dim, metric, algo) with `init_rapyer()`-time validation against vectorizer output (fail-fast).
- VECTOR index over the SF-key prefix, created at `init_rapyer()`.
- `.near('text', k=...)` KNN clause in `afind` + global similarity method; similarity score returned with results.
- Atomic hybrid KNN + boolean prefilter (Approach A, co-located TAG) — the headline differentiator, single `FT.SEARCH`.
- Real-Redis-only integration tests for KNN/index; fakeredis for store/cache/serialization only.

**Should have (competitive, v1.x / P2):**
- Distance/score threshold via `VECTOR_RANGE` — cheap once the render layer exists.
- Batch embedding on bulk `ainsert` (`aembed_many`) — ingestion perf.
- Cross-model global semantic search (heterogeneous hits) if v1 ships single-model only.
- HNSW tuning passthrough (`EF_RUNTIME`, build params); default FLAT (exact, simple) at launch.

**Defer (v2+ / P3):**
- Approach-B Lua `FT.SEARCH` hybrid for arbitrary parent-only prefilters — escape hatch; build only if co-located denormalization proves too limiting.
- Long-text chunking / multi-vector per field (`RedisTextChunks`?) — breaks the one-field-one-vector invariant; large scope.
- Embedding-model migration / re-index tooling.

**Explicit anti-features:** naive two-step hybrid (TOCTOU), fakeredis-backed KNN tests (fiction), bundling HF/torch in base, inline vector in parent JSON, auto re-embed on every save regardless of text change, exposing raw RediSearch query strings.

### Architecture Approach

RedisText slots into the existing SF machinery: `__init_subclass__` already classifies it as a special field; `asave_special()` rides `ensure_pipeline` so the parent `$.body_ref` `JSON.SET` and the SF `HSET` land in one MULTI/EXEC — but the embedding must be materialized *before* the pipeline opens (atomicity applies to the write, not the compute). The index+query machinery is isolated in a new real-Redis-only `vector/` package; the redisvl-touching code is isolated in a new `embeddings/` package behind a `Protocol`. See [ARCHITECTURE.md](ARCHITECTURE.md).

**Major components (NEW unless noted):**
1. `RedisText(SpecialFieldType)` (`rapyer/types/redis_text.py`) — HASH store (text, f32 blob, parent ref, co-located TAG mirror), `asave_special`/`aset_text`/`near()`.
2. `Vector(...)` annotation (`rapyer/fields/vector.py`) — index-time schema (dim/metric/algo/FLOAT32/HNSW), validated at class-build/init.
3. Embedding adapter (`rapyer/embeddings/adapter.py` + `protocol.py`) — pinned redisvl vectorizer + `EmbeddingsCache` wrapper, owns the thread-offload policy.
4. VECTOR index manager (`rapyer/vector/index.py`) — `FT.CREATE ON HASH` over the SF-key prefix, distinct shape/name from `idx:{ClassName}`.
5. `NearExpression` (extend `rapyer/fields/expression.py`) — renders `(<prefilter>)=>[KNN k @embedding $blob AS __dist]`, composes via `& | ~`; blob passed as PARAMS.
6. `init_rapyer()` + `RedisConfig` (MODIFIED) — register the VECTOR index and wire vectorizer/cache onto `Meta` during the unfrozen window; `_search_keys_by_query` extended for PARAMS + DIALECT 2 + index selection.

### Critical Pitfalls

Top items from [PITFALLS.md](PITFALLS.md) (all silent-wrong-until-production):

1. **FLOAT32 blob encoding (dtype/endianness/dim)** — numpy defaults to float64/native-endian; wrong width or byte order gives garbage distances with no error. Centralize in one helper: `np.asarray(vec, dtype=np.float32).tobytes()`; assert `len(blob) == dim*4`; cross-check `dim == vectorizer.dims` at init and fail-fast.
2. **Distance-metric confusion** — Redis does NOT normalize; IP + unnormalized = magnitude wins; COSINE returns a *distance* in [0,2], not similarity. Default COSINE; convert distance→similarity in exactly one place in the `.near()` result layer.
3. **Co-located TAG / vector drift** — denormalized parent filter fields (and the vector for edited text) go stale unless *every* mutation path (`asave`, `aupdate`, `ainsert`, `aduplicate`, nested `__setattr__`) re-projects into the HASH via the recursive SF save dispatch. Same class of bug as the nested-SF-drop fixed in 1.3.3.
4. **VECTOR index lifecycle collision** — reusing `idx:{ClassName}`/parent prefix collides with the JSON index; missing `DIALECT 2` fails only at first query; wrong `ON`/path silently empties results. Distinct name over `__rapyer_special__:` prefix, `FT.INFO` reconciliation + drop/rebuild/backfill on drift, separate code path from the JSON-index loop.
5. **EmbeddingsCache stale on model change** — `(text, model_name)` key returns old/wrong-dim vector when a model changes under a reused label. Bake `model_version`+`dim` into the cache key; treat dim as cache identity.
6. **Optional-extra import guard** — top-level `import redisvl` breaks base installs. Lazy guarded adapter, clear `RapyerError` pointing at the extra, and an extra-absent CI job.
7. **fakeredis false-green** — vector path must *raise* "requires real Redis" under fakeredis, never a silent no-op (the cascade `CascadeResult(0,0)` precedent). Add a `requires_vector_search` probe-and-skip gate; ensure CI's real Redis has vectors + DIALECT 2.

## Implications for Roadmap

Research points to five phases in a strict dependency order (adapter → type/save → index → query → fallback), plus a cross-cutting test/CI concern woven through all of them. Phase numbers continue from the current milestone (existing cascade work is Phases 1–5); label these logically as A–E and let the roadmapper assign real IDs.

### Phase A: Embedding adapter + `rapyer[embeddings]` extra
**Rationale:** Leaf dependency of everything; the only module that touches redisvl, isolating its API churn (spike 003). Independently testable on fakeredis (cache round-trip, dummy vectors) with no VECTOR index.
**Delivers:** `embeddings/adapter.py` + `protocol.py`, pinned to redisvl 0.23.0 API (`content=`), the `rapyer[embeddings]`/`-hf`/`-openai` extras, the FLOAT32 packing helper, the thread-offload policy (local vs API vectorizer), and the cache-key design (model-version+dim).
**Addresses:** auto-embed + EmbeddingsCache table stakes; batch-embed foundation.
**Avoids:** Pitfall 1 (FLOAT32 helper), 4 (cache key), 6 (client-embed sequencing discipline), 9 (guarded import), 10 (truncation handling).

### Phase B: `Vector[...]` annotation + `RedisText` SF type + atomic save path
**Rationale:** The save path defines the SF-key/HASH shape the index must target; must precede the index. De-risked by spike 001 (atomic combined save).
**Delivers:** `Vector(...)` annotation with dim/metric/algo/FLOAT32/HNSW params (validated at class-build/init); `RedisText.asave_special` HSET (text, blob, parent, TAG mirror) riding `ensure_pipeline`; `aset_text` recompute-on-text-change (dirty-check, no recompute on TTL refresh/unrelated mutation).
**Uses:** existing SF dispatch, `ensure_pipeline`, `_iter_special_fields`.
**Avoids:** Pitfall 3 (route every write through recursive SF save), 6 (compute-then-commit — vector materialized before pipeline opens). Fakeredis-testable for store/serialization; real Redis for the HASH write.

### Phase C: VECTOR index manager + `init_rapyer()` wiring — HIGHEST RISK
**Rationale:** The index must exist before any KNN query. Depends on B for key shape + annotation params. This is the single most error-prone integration point (Pitfall 7).
**Delivers:** `vector/index.py` — `FT.CREATE ON HASH` over the (tightly-scoped) SF prefix, distinct name (`idx:vec:{Class}:{field}` or shared `idx:__rapyer_text__`); `FT.INFO` reconciliation + drop/rebuild/backfill on schema drift; vectorizer/cache wired onto `Meta` during the unfrozen init window; guarded by `is_fake_redis`.
**Avoids:** Pitfall 1 (dim cross-check at init), 5 (FLAT default + migration-aware rebuild), 7 (distinct name, DIALECT, reconciliation, separate path). Real-Redis-only.

### Phase D: KNN query surface (default: co-located-TAG atomic hybrid)
**Rationale:** Meaningless without the index; the payoff phase. De-risked by spike 002 (Approach A).
**Delivers:** `NearExpression` rendering `(<prefilter>)=>[KNN k @embedding $blob AS __dist]`; extend `_search_keys_by_query` for PARAMS + DIALECT 2 + VECTOR-index selection; global `asearch_near(...)`; SF-key→parent resolution reusing `fetch_models_with_sf_loads`/`build_models_from_dumps`; distance→similarity score mapping in one place.
**Addresses:** `.near()` + global method + score + atomic hybrid (the headline).
**Avoids:** Pitfall 2 (score mapping), 3 (hybrid correctness tests across mutation paths). Real-Redis-only.

### Phase E: Test strategy / CI / version matrix (CROSS-CUTTING)
**Rationale:** Not deferrable — must be scoped alongside A–D, not after. fakeredis cannot do VECTOR/KNN by design.
**Delivers:** explicit split (fakeredis = store/serialization/cache/adapter; real Redis = KNN/index/hybrid under `tests/integration/`); a `requires_vector_search` probe-and-skip gate; an extra-absent CI job; a real-Redis service pinned to a RediSearch version with vectors + DIALECT 2.
**Avoids:** Pitfall 8 (false-green), 9 (extra-absent job).

**Optional / deferrable — Phase F: Approach-B Lua `FT.SEARCH` fallback.** For prefiltering on non-denormalized parent fields (KNN overfetch + N+1 `JSON.GET` inside `EVALSHA`). Spike 002 proved feasibility. Build only if parent-only filtering without denormalization is required this milestone; the Approach-A default (Phase D) satisfies the atomic-hybrid requirement alone.

### Phase Ordering Rationale

- **Strict dependency chain:** adapter is a leaf; save path defines the HASH/key shape; index targets that shape; query needs the index. This mirrors the "Suggested Build Order" all three of ARCHITECTURE/FEATURES/PITFALLS independently converged on.
- **fakeredis boundary drives phasing:** A–B are the only fakeredis-testable slices; C–D–F are integration-only. E must run in parallel so the boundary is enforced, not discovered.
- **Risk front-loading:** the adapter (A) contains redisvl churn early; the index (C) is flagged as highest-risk and gets migration/reconciliation rigor; the query (D) is last because it depends on everything.

### Research Flags

Phases likely needing deeper research / spike-level rigor during planning:
- **Phase C (index lifecycle):** HIGHEST risk. Open decisions on index *granularity* (one index per (model,field) vs one shared cross-model index per (dim,metric) — cross-model global KNN argues for shared, keyed by a `model` TAG) and *prefix scoping* (`__rapyer_special__:{Class}:` collides with other SF fields and multiple RedisText fields; needs a discriminator, e.g. a `__rapyer_vec__:` namespace or a TAG the index filters on). Flag for dedicated real-Redis verification.
- **Phase D (query / hybrid):** the `.near()` node is NOT a pure lazy render — it must trigger client-side query-text embedding before the search fires; subtlest seam with existing `afind`. Score-surfacing crosses the model/result boundary (sidecar result type vs. injected attribute) — a genuine design decision shared by `.near` and the global method.

Phases with standard/established patterns (lighter research):
- **Phase A (adapter):** de-risked by spike 003; redisvl API pinned and documented.
- **Phase B (SF save):** mirrors `RedisSet.asave_special` exactly; de-risked by spike 001.

### Open Decisions Requirements Must Resolve

1. **Index granularity + prefix scoping** (Phase C) — per-(model,field) vs shared-by-(dim,metric); discriminator to stop the SF prefix colliding with other SF fields / multiple RedisText fields. Cross-model global search (a shipped surface) pulls toward a shared index with a `model`/`parent` TAG.
2. **Co-located-TAG re-sync ownership** (Phase D) — Approach A requires the parent's `asave`/`aupdate`/`aduplicate`/nested `__setattr__` to re-project the TAG mirror into the SF HASH. Decide whether RedisText owns those fields or the parent write path does; scope the denormalized filter set narrowly (prefer Approach B for wide/arbitrary filters).
3. **EmbeddingsCache TTL vs rapyer TTL cascade** — recommend **independent**: the cache is recompute-avoidance, a third keyspace, never the source of truth for a field's vector, so it should not participate in the cascade keyset. Confirm.
4. **Vectorizer async thread-offload policy** — adapter routes local/CPU-bound vectorizers through `asyncio.to_thread` and awaits API vectorizers directly; confirm the detection mechanism (vectorizer type vs. real-`_aembed` probe) and that the offload also covers the blocking internal cache read for local vectorizers.
5. **Score representation at the model/result boundary** (Phase D) — sidecar result object vs injected attribute; must be consistent across `.near` and the global method.
6. **`Meta` freeze interaction** — vectorizer/cache handles must be assigned during the unfrozen `init_rapyer()` window (like `Meta.redis`); confirm they are plan-inputs vs derived (cf. the `cascade_function_name` exemption).
7. **`rapyer/init.py` merge markers** — the working tree currently has unresolved `<<<<<<< HEAD` conflict markers (shipped branch = the second block). Not a RedisText concern, but the Phase C init changes must land on the resolved file.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions + dep graph verified against PyPI JSON API + redisvl `main` source (2026-07-20); async-fallback read from source; team-locked redisvl decision. |
| Features | HIGH / MEDIUM | HIGH for query/index mechanics (RediSearch + redisvl docs + 3 VALIDATED spikes); MEDIUM for lifecycle/UX ergonomics (design-note judgment calls, flagged inline). |
| Architecture | HIGH | Grounded against real rapyer internals + 3 VALIDATED spikes; redisvl API confidence MEDIUM (pin/adapter mitigates). |
| Pitfalls | HIGH | RediSearch mechanics verified against Redis docs; ORM-specific pitfalls derived from the repo's own CONCERNS.md + design notes. |

**Overall confidence:** HIGH. The three feasibility spikes (001 KNN-over-SF-HASH + atomic save; 002 co-located-TAG hybrid + FT.SEARCH-in-Lua; 003 async EmbeddingsCache + API drift) removed the load-bearing unknowns before this synthesis.

### Gaps to Address

- **Index granularity / prefix scoping** — the biggest unresolved integration decision; resolve in Phase C planning with a real-Redis verification (see Open Decision 1).
- **redisvl API stability** — MEDIUM; contained by the exact pin + adapter + adapter-owned tests that re-validate on any bump.
- **Co-located-TAG re-sync ownership** — under-specified in the design note; must be nailed in Phase D requirements (Open Decision 2).
- **CI RediSearch version floor** — the 6.0–7.4 matrix may have cells lacking vector fields / DIALECT 2; the `requires_vector_search` gate must skip loudly (never false-green). Pin the minimum in Phase E.

## Sources

### Primary (HIGH confidence)
- rapyer feasibility spikes 001 / 002 / 003 (VALIDATED) — KNN over SF HASH prefix + atomic save; co-located-TAG hybrid + FT.SEARCH-in-Lua; async EmbeddingsCache + 0.7→0.23 API drift.
- PyPI JSON API (`redisvl` 0.23.0 `requires_dist`/`requires_python`) + redisvl `main` source (`vectorize/base.py`, `huggingface.py`, `schema/fields.py`) — versions, async-fallback, enums.
- rapyer internals — `types/special.py`, `types/redis_set.py`, `base.py`, `fields/expression.py`, `config.py`, `init.py`, `scripts/registry.py`.
- RediSearch vector docs (KNN `=>[KNN]`, `VECTOR_RANGE`, DIALECT 2, FLAT/HNSW, COSINE/L2/IP, FLOAT32/DIM); redisvl vectorizer + EmbeddingsCache docs.
- `.planning/notes/redistext-design-decisions.md`, `.planning/PROJECT.md` — locked decisions + milestone scope.
- `.planning/codebase/CONCERNS.md` — fakeredis/real-Redis divergences, nested-SF drop, N+1 FK precedents.

### Secondary (MEDIUM confidence)
- `.planning/research/questions.md` — open lifecycle/async questions (vectorizer async, hybrid syntax, cache keying vs rapyer TTL).
- Redis vector index tuning guidance (HNSW memory/recall tradeoffs).

---
*Research completed: 2026-07-20*
*Ready for roadmap: yes*
