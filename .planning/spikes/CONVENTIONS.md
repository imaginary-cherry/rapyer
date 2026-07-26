# Spike Conventions

Patterns established across the RedisText spike session. New spikes follow these
unless the question requires otherwise.

## Stack

- **Language:** Python (matches the `rapyer` package). Async via `redis.asyncio`, the
  same client rapyer uses.
- **Redis:** real Redis Stack on **:6370** (RediSearch 2.10 + ReJSON 2.08). fakeredis
  is out of scope for the vector path by design.
- **Optional deps:** run redisvl-dependent spikes with `uv run --with redisvl python
  spike.py` so the project env stays clean (redisvl is a `rapyer[embeddings]` extra).

## Structure

- One dir per spike: `.planning/spikes/NNN-name/{spike.py, README.md}`.
- Each `spike.py` is self-contained, hardcodes config, cleans up its own keys/indexes
  on entry and exit, and prints observable pass/fail lines.
- Ad-hoc API probes go in the scratchpad, not the spike dir.

## Patterns

- **SF-key modeling:** mimic `SpecialFieldType.special_field_key` —
  `__rapyer_special__:{space}:{parent}:body`. Vectors live here, referenced from the
  parent JSON doc.
- **Vector encoding:** `struct.pack("<{n}f", *vec)` → little-endian FLOAT32 blob for
  RediSearch; pass via `PARAMS 2 q <blob>` with `DIALECT 2`.
- **KNN query:** `*=>[KNN k @embedding $q AS dist]`, `SORTBY dist`. Hybrid prefilter:
  `(@tag:{v})=>[KNN ...]`.
- **Atomicity:** every user-level action = one server-side op. Multi-key writes and
  hybrid search-then-filter go through a single `EVAL`/`EVALSHA`. `FT.SEARCH`,
  `JSON.SET`, `JSON.GET`, `HSET` are all callable from Lua on this Redis Stack.
- **Comment style:** one-line comments only, one-line module/function docstrings
  (project hook enforces this even for spikes); avoid triple-quoted multi-line string
  literals — the hook misreads them as multi-line comments.

## Tools & Libraries

- `redis` (redis-py) 7.0.1 — in project env, has `redis.asyncio`.
- `redisvl` 0.23.0 — **API drifted from the 0.7.0 docs** (`content` not `text`); target
  the installed API and wrap it behind a thin adapter. Pin the version.
