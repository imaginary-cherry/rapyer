---
spike: 003
name: redisvl-embeddingscache-async
type: standard
validates: "Given redisvl's EmbeddingsCache, when aset/aget/amset/amget/aexists/adrop run against Redis Stack, then text+vector+metadata round-trip in an async flow with working TTL"
verdict: VALIDATED
related: [001]
tags: [redisvl, cache, async, ttl]
---

# Spike 003: redisvl EmbeddingsCache (async)

## What This Validates

redisvl's `EmbeddingsCache` (the embedding-dedup layer chosen for RedisText) works in
rapyer's async model against the real Redis Stack, with dummy vectors (no torch/HF).

## Research

Docs (redisvl 0.7.0) showed `set(text=..., model_name=..., embedding=..., metadata=...)`
and `a`-prefixed async variants. Installed version resolved to **0.23.0**, whose API
has drifted — validated the real signatures empirically.

## How to Run

```
uv run --with redisvl python spike.py
```

(redisvl is not in the project env by design — it is an optional `rapyer[embeddings]`
extra.)

## Investigation Trail

- First run failed: `aset()` has no `text` kwarg. Introspected signatures — the param
  is now `content`.
- Probed the return dict and batch-item schema: `aget` returns
  `{entry_id, content, model_name, embedding, inserted_at, metadata}`; `amset` items
  key on `content`.
- Fixed the script to the 0.23.0 API; all async ops pass.

## Results

**VALIDATED.** All async operations succeed against :6370:

- `aset` → `aget` round-trips content, embedding (as floats), and metadata.
- `amset`/`amget` batch: 2 set, 2 hits.
- `aexists` True before / False after `adrop`.
- Per-entry TTL: present immediately, expired after 1.5s (ttl=1).

### API drift (0.7.0 docs → 0.23.0 installed) — build must target the real API

| Docs (0.7.0) | Installed (0.23.0) |
|--------------|--------------------|
| `set(text=...)` | `set(content=...)` |
| result `{text, ...}` | result `{entry_id, content, model_name, embedding, inserted_at, metadata}` |
| `mset` items `{text, ...}` | `mset` items `{content, ...}` |

### Signal for the build

- **`EmbeddingsCache` is a third, independent keyspace**: `{name}:{sha256(content)}`,
  keyed by content hash + model_name. Separate from the RedisText SF key and the parent
  model doc. Design must decide how (if at all) it coordinates with the SF store — it is
  a *dedup/recompute-avoidance* layer, not the source of truth for a field's vector.
- **`rapyer[embeddings]` extra is lean**: redisvl core install = ~13 packages (numpy
  the heaviest). Torch/sentence-transformers only arrive with HF vectorizers, which are
  a separate opt-in.
- **Pin/guard the redisvl version** — the `content`/`text` drift proves the API is not
  stable across minors. Wrap it behind a thin rapyer adapter so version changes are
  contained.
- Per-entry TTL works → can align with rapyer's TTL/cascade behavior if desired.
