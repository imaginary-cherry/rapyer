# Spike Manifest

## Idea

Prove the end-to-end feasibility of a `RedisText` special field type: text stored
with a vector embedding under its own Redis key, KNN-searchable via a RediSearch
`VECTOR` index, before committing to a full RedisText milestone. Embeddings are
computed by a redisvl vectorizer and cached via redisvl `EmbeddingsCache` (optional
`rapyer[embeddings]` extra). fakeredis is out of scope by design — the vector path is
real-Redis-only (Redis Stack on :6370).

## Requirements

Design decisions locked during exploration + spiking. Non-negotiable for the build.

- **RedisText is a Special Field Type**, stored under its own key
  (`__rapyer_special__:{model_key}:{field_path}`), referenced from the parent JSON
  doc — never inline. Leading structure: HASH.
- **The `VECTOR` index is built over the SF-key prefix**, not the parent model docs.
  KNN returns SF keys that resolve back to parent models via the reference.
- **Every user-level action must be atomic — a single server-side op.** No
  multi-round-trip sequences (TOCTOU / race risk). Save (vector + parent ref) is one
  atomic Lua/`EVALSHA`; hybrid KNN+filter must be a single atomic op, not a
  client-side two-step.
- **redisvl is an optional extra** (`rapyer[embeddings]`); base installs stay lean.
- **Query API** = a `.near()` Expression node composing inside `afind(...)` **and** a
  top-level global similarity method.

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001 | vector-knn-sf-key | comparison | KNN over separate SF keys (HASH vs JSON) returns ranked keys resolving to parents | ✓ VALIDATED (HASH=JSON; atomic save works) | vector, knn, redisearch, sf |
| 002 | hybrid-crosskey-prefilter | standard | Atomic single-op KNN+boolean prefilter given vector-in-SF-key / filters-in-parent split | ✓ VALIDATED (A co-locate + B FT.SEARCH-in-Lua both atomic) | vector, hybrid, atomicity, lua |
| 003 | redisvl-embeddingscache-async | standard | redisvl EmbeddingsCache async round-trip (aset/aget/amget) with TTL | ✓ VALIDATED (works async; API drift 0.7→0.23, 3rd keyspace) | redisvl, cache, async |
