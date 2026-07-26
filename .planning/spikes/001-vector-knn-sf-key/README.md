---
spike: 001
name: vector-knn-sf-key
type: comparison
validates: "Given text+vector stored under separate __rapyer_special__: keys, when a VECTOR index over that prefix runs KNN via redis.asyncio, then ranked SF keys return and resolve to parent model keys"
verdict: VALIDATED
related: [002, 003]
tags: [vector, knn, redisearch, sf, atomicity]
---

# Spike 001: KNN over separate SF keys (HASH vs JSON)

## What This Validates

Given text + a vector stored under their own `__rapyer_special__:{model_key}:body`
keys (the SpecialField pattern), when a RediSearch `VECTOR` index built over that
key prefix runs a KNN query via `redis.asyncio`, then ranked SF keys are returned and
resolve back to their parent model. Compares HASH vs JSON storage, and demonstrates an
atomic combined save.

## Research

RediSearch KNN syntax (DIALECT 2): `*=>[KNN k @field $blob AS dist]` with the query
vector passed via `PARAMS 2 blob <float32-bytes>`. Vector declared FLAT/HNSW + TYPE
FLOAT32 + DIM + DISTANCE_METRIC. HASH stores the vector as a raw little-endian float32
blob; JSON stores it as a numeric array. Empirical validation on the live Redis Stack
(:6370, RediSearch 2.10, ReJSON 2.08) was preferred over doc-reading.

## How to Run

```
python spike.py
```

## What to Expect

Article:1 (nearest to the query vector) ranked first, Article:2 second, a food
article last; identical distances between HASH and JSON; atomic save reports both
keys present.

## Investigation Trail

- Built a dim-4 corpus of 4 docs (2 "ai", 2 "food") stored under SF-style keys.
- Created two indexes over two SF sub-prefixes: `idx:sf_hash` (ON HASH) and
  `idx:sf_json` (ON JSON), each with a `VECTOR` field + `parent`/`category` TAGs.
- Ran identical KNN queries against both.
- Added an `EVAL` that writes the SF HASH (vector) **and** the parent JSON `body_ref`
  in one script, to prove the atomic save requirement is achievable.

## Results

**VALIDATED.** Evidence from the run:

- KNN over the SF-key prefix works. Ranking correct: `Article:1` dist `0.000242`,
  `Article:2` dist `0.00331`, `Article:4` (food) dist `0.727`.
- **HASH and JSON produce identical distances** — either storage works for the vector.
  HASH is the leaner, more classic vector structure and fits the SF native-structure
  convention (SET/ZSET); JSON is viable if we want the SF value human-readable.
- Each result row carries the `parent` field (`Article:N`) → **resolves to the parent
  model key**, satisfying the "SF key references parent" requirement.
- **Atomic combined save works:** one `EVAL` did `HSET` (vector into SF key) +
  `JSON.SET` (`$.body_ref` into parent doc); both landed. Confirms the save path can be
  a single server-side atomic op (module commands `HSET`/`JSON.SET` both callable from
  Lua).

### Signal for the build

- Store the RedisText SF value as a **HASH** with fields `text`, `embedding`
  (float32 blob), `parent`, plus any co-located filterable fields (see spike 002).
- Vector index is a new shape: `ON HASH PREFIX __rapyer_special__:...` — distinct from
  the per-model `idx:{ClassName}` JSON indexes.
- Save = one Lua/`EVALSHA` writing SF HASH + parent ref, extending the existing SF
  save-snippet dispatch.
