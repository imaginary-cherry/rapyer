---
title: RedisText (text + embeddings) — design decisions
date: 2026-07-20
context: /gsd:explore session — designing a new Redis field type for text with vector embeddings
---

# RedisText — Design Decisions

A new `RedisText` field type: stores text **plus** a vector embedding, and is
semantically searchable (KNN) across models. Decisions locked during exploration.

## Locked decisions

1. **Scope = full slice.** The milestone delivers text + cached embedding on the
   field **and** KNN similarity search via `afind`. Cohesive feature; expected to
   decompose into multiple phases.

2. **Embeddings via redisvl, as an optional extra.** Depend on `redisvl` but only
   through an install extra (e.g. `rapyer[embeddings]`), wrapping redisvl's
   vectorizers + `EmbeddingsCache` directly. Heavy deps (HF/torch) are pulled only
   when the user opts in; base installs stay lean.

3. **`EmbeddingsCache` is a cache, not a search index.** redisvl's `EmbeddingsCache`
   hashes `(text, model_name)` → stores `{text, embedding, metadata}` with optional
   TTL, and does **exact-text lookup only** — no similarity search. It sits in front
   of a vectorizer to avoid recomputation. Similarity search is a *separate*
   capability requiring a RediSearch `VECTOR` index.

4. **Query API = expression node + global method.** A `.near('query text', k=...)`
   Expression node that composes inside `afind(...)` with `& / | / ~` (enabling
   hybrid KNN + boolean prefilter), **and** a top-level rapyer method for global
   similarity queries. Both surfaces ship.

5. **Atomicity boundary.** Embedding computation cannot be server-side atomic — a
   vector is produced client-side (local HF model or remote API) *before* anything is
   written. Keep the **write** atomic: text and vector land together in one
   pipeline/`JSON.SET`. The text→vector step lives outside Redis by necessity.

6. **fakeredis is unsupported for the ENTIRE RedisText feature — by design.** Not an
   open question, and not limited to the KNN path. Every layer — adapter, store,
   serialization, index, KNN, hybrid — is real-Redis-only (Redis Stack on :6370).
   fakeredis is **not used anywhere** in this feature (no store/cache/serialization
   unit tests on fakeredis either). Using `RedisText` against a fakeredis client must
   raise a clear "requires real Redis" error, never silently no-op.

7. **RedisText is a Special Field Type (SF), not inline JSON.** Like `RedisSet` and
   `RedisPriorityQueue`, the text + vector live under their **own** Redis key
   (`__rapyer_special__:{model_key}:{field_path}`), referenced from the parent JSON
   doc — never embedded inline. A HASH is the leading storage structure (classic
   RediSearch vector pattern, fits the SF native-structure convention). The
   RediSearch `VECTOR` index is built over the SF-key prefix, **not** over the parent
   model docs; KNN returns SF keys that resolve back to parent models via the ref.

8. **Every user-level action must be atomic — one server-side op.** No multi-round-trip
   sequences per single user action (TOCTOU / race-condition risk). Implications:
   - **Save:** vector→SF key + parent reference update = one atomic Lua/`EVALSHA`
     (reuse the existing SF save-snippet dispatch), not two client writes.
   - **Hybrid KNN+filter query:** the naive two-step (KNN → resolve parents → filter)
     is **disallowed** — two round-trips can interleave with other writers. Must be a
     single atomic op: either (A) co-locate filterable fields into the SF HASH so one
     `FT.SEARCH` does KNN+prefilter, or (B) a Lua script running `FT.SEARCH` KNN +
     parent filtering internally in one `EVALSHA`. Whether `FT.SEARCH` is callable
     from inside Lua is an open feasibility question (see spike 002).

## Implied schema constraint

Vector index parameters are **index-time schema**, so they must be declared at the
field-annotation level (mirroring `Index[...]`):

- embedding **dim** (must match the chosen model's output size)
- **distance metric** — cosine / L2 / inner-product
- **algorithm** — FLAT vs HNSW (+ HNSW build/query params)
- vector **type** — FLOAT32

The vectorizer instance + Redis connection are wired at `init_rapyer()` time (like
`Meta.redis`), while per-field vector params come from the annotation. The `VECTOR`
index is created over the **SF-key prefix** (`__rapyer_special__:...`), not the
parent model prefix — a new index shape distinct from the existing per-model
`idx:{ClassName}` JSON indexes.

## Open items

See `.planning/research/questions.md` for the remaining research questions
(vectorizer async story, hybrid KNN query syntax, `EmbeddingsCache` keying vs
rapyer key/TTL scheme). A feasibility spike precedes planning; a dedicated
`/gsd:new-milestone` follows once the spike confirms feasibility.
