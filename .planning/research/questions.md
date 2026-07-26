# Research Questions

Open questions surfaced during exploration, pending deeper investigation.

## RedisText (text + embeddings) — 2026-07-20

- **Vectorizer async story.** Are redisvl vectorizers (`HFTextVectorizer`, API-backed
  vectorizers) async-native? How do they fit rapyer's async-first + implicit-pipeline
  model, given local HF inference is CPU/GPU-bound and synchronous? Do we offload to a
  thread, require async vectorizers, or both?

- **RediSearch hybrid KNN syntax.** Exact query form for combining a `.near()` KNN
  clause with a boolean prefilter (the `.near(...) & (Model.field == x)` composition):
  RediSearch `=>[KNN k @vec $blob]` syntax, prefilter placement, `EF_RUNTIME`, and how
  the `Expression` tree renders it.

- **`EmbeddingsCache` keying vs rapyer scheme.** How does redisvl's `(text, model_name)`
  hash-keyed cache interact with rapyer's key derivation and the just-shipped TTL
  cascade? Does the cache TTL need to participate in cascade, or stay independent?

> Note: "Does fakeredis support VECTOR/KNN?" is **not** an open question — decided:
> unsupported by design, vector path is real-Redis-only. See
> `.planning/notes/redistext-design-decisions.md`.
