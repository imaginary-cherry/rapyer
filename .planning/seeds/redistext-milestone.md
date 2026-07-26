---
title: RedisText milestone — text + embeddings + KNN search
trigger_condition: Feasibility spike confirms redisvl EmbeddingsCache + RediSearch VECTOR KNN work in rapyer's async/pipeline model on real Redis Stack
planted_date: 2026-07-20
---

# Seed: RedisText milestone

Once the feasibility spike passes, start a dedicated milestone via
`/gsd:new-milestone` for the `RedisText` field type. This is milestone-sized and
separate from the TTL-cascade milestone.

## Scope (from exploration)

Full slice — a `RedisText` field that:
- stores text + a vector embedding, embedding computed via a redisvl vectorizer and
  cached via redisvl `EmbeddingsCache` (optional `rapyer[embeddings]` extra);
- is KNN-searchable via a `.near()` Expression node inside `afind(...)` **and** a
  top-level global similarity method;
- declares vector schema (dim, metric, algorithm, type) at the field-annotation level.

## Likely phase decomposition (rough)

1. `RedisText` type + store/serialize text + vector inline; vectorizer/cache wiring
   at `init_rapyer()`; `rapyer[embeddings]` extra. (fakeredis-testable layer only.)
2. RediSearch `VECTOR` index creation from field annotations (extends `Index[...]`
   / `redis_schema` / `acreate_index`). (real-Redis-only.)
3. KNN query surface: `.near()` Expression node + hybrid prefilter + global search
   method. (real-Redis-only.)

## Cross-references

- Design decisions: `.planning/notes/redistext-design-decisions.md`
- Open questions: `.planning/research/questions.md`
