# Stack Research

**Domain:** Atomic server-side multi-key TTL propagation over a RedisJSON (Redis Stack) FK graph, in an async Python ORM (`rapyer`)
**Researched:** 2026-07-06
**Confidence:** HIGH (redis-py APIs, Lua sandbox rules, RedisJSON-from-Lua, cluster cross-slot verified against official docs; MEDIUM on fakeredis JSON-in-Lua parity)

> **Milestone framing.** This is an additive slice on a mature codebase. The stack recommendation is deliberately *conservative*: reuse the existing EVALSHA + template/variant + SF-dispatch machinery rather than introduce new runtime primitives. No new third-party dependency is required to ship TTL cascade. The "stack" here is really *which Redis/Lua/redis-py primitives to compose* and *which to avoid*.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `redis-py` (`redis.asyncio`) | keep existing pin `>=6.0.0,<7.5.0` (locked `7.0.1`) | Async client: `evalsha`, `pipeline.evalsha`, `script_load`, `expire`/`pexpire` | Already the sole client. Every primitive cascade needs (`EVALSHA`, transactional pipeline, `EXPIRE`) has existed since redis-py 4.x/5.x — **no version bump needed**. Do **not** move to redis-py 8.x this milestone (see "What NOT to Use"). |
| Redis Stack server (RedisJSON) | tox matrix 6.0–7.4; CI image `redis-stack-server:7.4.0-v8` | `JSON.GET`/`JSON.SET` docs + `EXPIRE` for TTL | Cascade must read FK key-strings out of parent JSON *server-side*; RedisJSON commands are callable from Lua via `redis.call('JSON.GET', ...)`. Verified. |
| Server-side Lua (EVAL/EVALSHA) | Lua 5.1 (embedded) | The single atomic traversal-and-expire unit | Only mechanism that can *read a parent doc, branch on its contents, follow FK key-strings, and apply `EXPIRE` to N keys* in one atomic server-side step. Transactional pipelines (MULTI/EXEC) cannot read-then-branch mid-transaction — a hard blocker for graph traversal. |
| Existing `rapyer.scripts` machinery | in-repo | Template load → variant substitution → SF-style dispatch injection → `SCRIPT LOAD` → cached SHA → `EVALSHA` with `NoScriptError` self-heal | The cascade script slots directly into `SCRIPT_REGISTRY` + `_inject_sf_dispatch` pattern. A **per-model-class FK-path dispatch table** (analogous to `SF_SAVE`/`SF_LOAD`) is the natural extension point. |

### Redis command primitives (the actual building blocks)

| Primitive | Use in cascade | Notes |
|-----------|----------------|-------|
| `redis.call('JSON.GET', key, path)` from Lua | Read a node's FK fields to discover child key-strings | On real Redis a `$`-rooted path returns a **JSON array string** (`[value]`); the existing `EXTRACT_*`/`DICT_EXTRACT_*` variant substitution in `loader.py` exists precisely to unwrap this — reuse that pattern, `cjson.decode(...)[1]`. |
| `redis.call('EXPIRE', key, ttl)` / `PEXPIRE` | Apply the parent's TTL to each traversed key | `Meta.ttl` is integer **seconds** today → use `EXPIRE`. Under Redis 7.0 effects-replication (the only mode), `EXPIRE` inside a script is replicated as a deterministic effect — the classic "EXPIRE is non-deterministic in scripts" warning **no longer applies**. HIGH confidence. |
| `redis.call('EXISTS', key)` | Skip missing/already-expired children; cheap cycle guard companion | Mirrors `get_or_create.lua`'s existence-sentinel idiom. |
| `cjson.decode` / `cjson.encode` | Parse `JSON.GET` output, encode a visited-set / return payload | Ships in the Lua sandbox. HIGH confidence. |
| Lua table as `visited` set | Cycle safety + max-depth guard, keyed by full key-string | FK graphs may cycle (self-ref FKs resolve globally per `relational.py`). A `local visited = {}` set + integer depth counter is the standard, allocation-cheap approach. Must be `local` (globals are blocked in the sandbox). |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `fakeredis[lua,json]` | keep `>=2.20.0` (locked `2.34.1`) | Unit-test substitute (lupa Lua 5.1 + jsonpath-ng JSON) | Already the unit tier. Cascade scripts run under it, but **verify JSON.GET-from-Lua parity early** (see Pitfalls / What NOT to Use). |
| `pydantic` v2 | keep `>=2.11.0,<2.14.0` (locked `2.12.5`) | `CascadeTTL` config object modelled as a pydantic model/dataclass on the FK field | Mirrors how `RedisConfig`/annotations are already modelled; no new dep. |

No new package needs to be added to `pyproject.toml` for this milestone. **HIGH confidence.**

## Installation

```bash
# Nothing new to install. Existing locked stack already carries every primitive:
#   redis==7.0.1  (redis.asyncio: evalsha, script_load, expire, pipeline)
#   fakeredis[lua,json]==2.34.1  (Lua 5.1 via lupa, JSON via jsonpath-ng)
#   pydantic==2.12.5
# Verify the environment (no changes expected):
uv sync --locked --group dev
```

## Architecture-shaping decision: where does traversal happen?

Two viable shapes (PROJECT.md defers this to research). The **stack facts** favor a hybrid:

**Option A — Full server-side Lua traversal (one EVALSHA).** Script reads parent JSON, extracts FK key-strings, recurses, applies `EXPIRE`, tracks `visited`/depth. Truest "single atomic op." Requires a **class→FK-JSONPath dispatch table** injected at `register_scripts()` time (the child's class is derivable from its `"ClassName:pk"` key, and each class's FK paths + per-relationship `CascadeTTL` are known at registration — exactly the `_inject_sf_dispatch` plugin pattern).

**Option B — Python pre-resolves the key set, one atomic apply.** Python BFS/DFS via `afetch` collects every cascade key, then a *single* `EVALSHA`/MULTI-EXEC applies all `EXPIRE`s. Simpler Lua, but the traversal reads are multi-round-trip and TOCTOU-prone (graph can mutate between read and apply).

**Recommendation: Option A**, because the milestone's stated core value is atomic, server-side, at-set-time propagation with no TOCTOU gap — only server-side traversal satisfies "no TOCTOU gap." Option B's final apply is atomic but its *discovery* is not, so a child added mid-traversal is missed. Keep Option B's key-resolution logic as the **fakeredis fallback / debugging path** if JSON-in-Lua parity proves too weak (MEDIUM confidence this fallback is needed). Either way, `_ttl_keys()` (main key + SF keys) is the per-node key expansion already implemented — the cascade layers *on top* of it per visited node.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| EVALSHA (existing machinery) | **Redis Functions / `FCALL`** (persisted libraries, no SHA/NOSCRIPT bookkeeping — the *2026 "recommended for new code" path*) | If rapyer ever drops Redis < 7.0 **and** fakeredis gains FUNCTION support **and** the team wants a from-scratch programmability layer. **Not now:** FUNCTION needs Redis 7.0+ (breaks the 6.0 tox rung), is not reliably emulated by fakeredis, and would fork the whole `scripts/` layer for zero user-visible benefit this milestone. |
| Server-side Lua traversal | Python-side traversal + single atomic apply (Option B above) | As a fakeredis fallback, or if JSON-from-Lua parity blocks the pure-Lua path. |
| `EXPIRE` (seconds) | `PEXPIRE` (ms) / `EXPIREAT` | Only if `CascadeTTL` later grows sub-second or absolute-deadline semantics. Today `Meta.ttl` is integer seconds — `EXPIRE` matches. |
| Recursive `JSON.GET` per node | `JSON.OBJKEYS` / `JSON.TYPE` for schema discovery | FK JSONPaths are **known from the model schema at registration** — no need to introspect the doc shape at runtime. Prefer passing known paths (via dispatch table) over scanning object keys. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Redis Cluster with cross-node cascade** | Discovered child keys hash to arbitrary slots/nodes. A Lua script may only touch keys on **one node/slot**; touching keys on another node is *physically impossible*, not just guarded. `allow-cross-slot-keys` (shebang flag, 7.0+) only relaxes *same-node* multi-slot, not cross-node. rapyer's keys (`ClassName:pk`, `__rapyer_special__:...`) carry **no hash tags**, so a cluster deploy would `CROSSSLOT`-fail the moment cascade crosses an FK. | Document cascade as **standalone / non-cluster only** for this milestone. (Future: hash-tag co-location or client-side fan-out — out of scope.) HIGH confidence. |
| **`KEYS` / `SCAN` inside the cascade script to find children** | The Lua sandbox contract: a script must only access keys it was *given*, never programmatically-derived ones. `KEYS`-pattern scanning is O(N) over the keyspace and breaks cluster/replication guarantees. | Follow explicit FK key-strings read from the parent JSON (`JSON.GET`), bounded by max-depth + `visited` set. |
| **Global variables in the Lua script** | Sandbox blocks global declaration/access ("Script attempted to create global variable"). Easy to trip when accumulating a visited-set or counter. | Everything `local` (`local visited = {}`, `local depth = ...`). Matches existing scripts. |
| **`require`/external Lua modules** | Disabled in the sandbox. | Only `cjson`, `cmsgpack`, `struct`, `bit`, `table`, `string`, `math` are available. `cjson` is all cascade needs. |
| **Bumping to redis-py 8.x** (out of current `<7.5.0` pin) | redis-py 8.0 defaults the wire to **RESP3**. Lua `redis.call` reply shapes and the `JSON.GET` array-unwrapping the codebase relies on (the `EXTRACT_*` variant substitutions, `cjson.decode(...)[1]`) are RESP2-shaped assumptions. A silent RESP2→RESP3 switch risks subtly corrupting the existing scripts *and* the new cascade one. | Stay within the existing `>=6.0.0,<7.5.0` pin. Revisit RESP3 as its own dedicated milestone. HIGH confidence. |
| **Relying on `redis.replicate_commands()` / verbatim replication semantics** | Deprecated in 7.0; verbatim replication removed entirely in 7.0 (effects-only). Any script written assuming verbatim replication is wrong on modern servers. | Write for effects replication (the default and only mode). This is what *makes* `EXPIRE` safe in-script — lean into it. |
| **MULTI/EXEC transactional pipeline for the traversal itself** | Cannot read-then-branch mid-transaction (documented codebase limit). Graph traversal is inherently read→decide→read. | Lua (`EVALSHA`) for the traversal; a pipeline may still *wrap* the single `EVALSHA` call (via `run_sha`) to co-batch with other writes at set-time. |
| **Assuming fakeredis == real Redis for JSON-in-Lua** | fakeredis emulates JSON via jsonpath-ng and Lua via lupa *separately*; `redis.call('JSON.GET', ...)` **from inside Lua** is a known thin/divergent spot (the repo already maintains `FAKEREDIS_VARIANT` vs `REDIS_VARIANT` because JSON.GET reply shapes differ). MEDIUM confidence it will need a variant branch or an Option-B fallback for the cascade script. | Add a real-Redis integration test for cascade from day one; do not trust green fakeredis alone. Budget a variant branch in `loader.py`'s `VARIANTS`. |

## Stack Patterns by Variant

**If deploying on standalone Redis Stack (the supported case):**
- Full server-side Lua cascade (Option A), `EVALSHA` via existing `arun_sha`/`run_sha`, `EXPIRE` per visited key, `visited` table + integer `depth` guard.
- Because it delivers the one-atomic-op / no-TOCTOU guarantee the milestone requires.

**If a user runs Redis Cluster:**
- TTL cascade across FKs is **unsupported** (cross-node keys). Detect and either no-op-with-warning or raise a clear `RapyerError`.
- Because cross-node multi-key writes are impossible in a single Lua invocation regardless of flags.

**If the JSON-from-Lua fakeredis path proves too weak in tests:**
- Fall back to Option B (Python resolves keys, single atomic `EXPIRE` apply) *for the fakeredis variant only*, keeping Option A on real Redis.
- Because unit-tier coverage must stay green without weakening the production atomicity story.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `redis==7.0.1` (client) | Redis server 6.0–7.4 | All cascade primitives present; effects-replication default on 7.x, effects-default-since-5.0 on 6.0. `EXPIRE`-in-script safe across the whole matrix. |
| `redis` client `<7.5.0` pin | RESP2 wire assumptions | Existing `EXTRACT_*`/`cjson.decode(...)[1]` unwrap logic depends on RESP2 reply shapes. Do not cross into 8.x (RESP3 default) without a dedicated migration. |
| `fakeredis==2.34.1` `[lua,json]` | lupa Lua 5.1, jsonpath-ng | Lua sandbox parity is *approximate*; `FUNCTION`/`FCALL` unsupported (reinforces staying on EVALSHA); JSON-in-Lua is the risk area. |
| Redis server 7.0+ | effects-only replication | Verbatim replication removed; `redis.replicate_commands()` a no-op. Write scripts accordingly. |

## Sources

- https://redis.io/docs/latest/develop/programmability/lua-api/ — sandbox rules (no globals, no `require`), available libs (`cjson`), `redis.call`, script flags incl. `allow-cross-slot-keys`/`no-cluster`, effects-replication-only as of 7.0, `SELECT`/RESP notes. **HIGH.**
- https://redis.io/docs/latest/develop/programmability/eval-intro/ + PR redis/redis#5208 — non-deterministic-command / EXPIRE determinism history, effects vs verbatim replication. **HIGH.**
- https://redis.io/docs/latest/commands/json.get/ , https://redis.io/docs/latest/commands/json.objkeys/ — RedisJSON commands callable via `redis.call`, `$`-path array-wrapping. **HIGH.**
- https://redis.io/blog/redis-clustering-best-practices-with-keys/ + repost.aws/knowledge-center/elasticache-crossslot-keys-error-redis + hackernoon CROSSSLOT guide — cluster same-slot / CROSSSLOT constraint on multi-key + Lua. **HIGH.**
- https://redis.readthedocs.io/en/stable/lua_scripting.html (redis-py 8.0 docs) + https://redis.io/docs/latest/develop/programmability/functions-intro/ — `register_script`/`Script` NOSCRIPT self-heal, `EVALSHA(_RO)`, FCALL vs EVALSHA tradeoffs, redis-py 8.0 RESP3-default caveat. **HIGH** (RESP3-default), **MEDIUM** on exact 8.0 behavioral edges.
- https://fakeredis.readthedocs.io/en/latest/redis-stack/ + github.com/cunla/fakeredis-py#304 — fakeredis JSON via jsonpath-ng, Lua via lupa (5.1), scripting-support limits. **MEDIUM.**
- In-repo verification: `rapyer/scripts/registry.py`, `rapyer/scripts/loader.py`, `rapyer/scripts/lua/atomic/get_or_create.lua`, `rapyer/base.py` (`_ttl_keys`, `refresh_ttl`, `aset_ttl`, `_all_keys_for_key`). **HIGH** (existing machinery + extension points).

---
*Stack research for: atomic server-side TTL cascade over a RedisJSON FK graph*
*Researched: 2026-07-06*
