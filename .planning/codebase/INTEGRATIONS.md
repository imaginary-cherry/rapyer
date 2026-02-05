# External Integrations

**Analysis Date:** 2026-02-05

## APIs & External Services

**None Detected** - This is a library/ORM, not a service integration layer. Rapyer itself provides no external API calls or integrations.

## Data Storage

**Databases:**
- Redis (6.0+, up to 7.0)
  - Connection: `RedisConfig.redis` or via `init_rapyer(redis=...)`
  - Default URL: `redis://localhost:6379/0`
  - Client: `redis-py` async client (`redis.asyncio.Redis`)
  - Module requirement: Redis JSON module for optimized JSON field storage
  - Query support: Redis Search via `redis.commands.search` (indexes only, not data retrieval)

**File Storage:**
- None - Data stored entirely in Redis, no file storage integration

**Caching:**
- Redis - Used as primary data store, not as cache layer
- TTL support via `RedisConfig.ttl` parameter (optional)
- Automatic TTL refresh on read/write operations (configurable via `refresh_ttl`)

## Authentication & Identity

**Auth Provider:**
- Custom/None - No built-in authentication provider integration
- Redis authentication: Handled via connection string passed to `init_rapyer()`
  - Example: `redis://:password@host:6379/0`
  - Managed by `redis-py` client library

## Monitoring & Observability

**Error Tracking:**
- None - No integration with error tracking services (Sentry, etc.)

**Logs:**
- Python `logging` module
- Logger integration via `init_rapyer(logger=...)` parameter
- Rapyer logger name: `"rapyer"` (can be configured via `logging.getLogger("rapyer")`)

## CI/CD & Deployment

**Hosting:**
- Not applicable - Rapyer is a library, not a hosted service
- Deployed as PyPI package: `https://pypi.org/project/rapyer/`

**CI Pipeline:**
- GitHub Actions (via `.github/workflows/`)
- Test matrix: Python 3.10-3.13 × Redis 6.0-6.4 × Pydantic 2.11-2.12
- Runs via tox for multi-environment testing

## Environment Configuration

**Required env vars:**
- `REDIS_DB` (optional) - Passed via tox `passenv = REDIS_DB`
- No other environment variables required

**Secrets location:**
- Redis credentials embedded in connection URL passed to `init_rapyer()`
- No `.env` file mechanism detected

## Webhooks & Callbacks

**Incoming:**
- None - This is a library, not a service with webhooks

**Outgoing:**
- None - No outgoing webhook or callback integrations

## Lua Scripting

**Redis Lua Scripts:**
- Location: `rapyer/scripts/lua/` - Contains atomic operation implementations
- Loaded at runtime via `register_scripts()` in `rapyer/init.py`
- Script types:
  - `numeric/*` - Arithmetic operations (mul, floordiv, mod, pow, truediv)
  - `string/*` - String operations (append, mul)
  - `list/*` - List operations (remove_range)
  - `datetime/*` - DateTime arithmetic (add)
  - `dict/*` - Dict operations (pop, popitem)
- Registration: Scripts are loaded and cached by SHA at initialization time
- Error handling: `NoScriptError` triggers re-registration if script lost from Redis memory
- Dual variants: `redis` variant (standard Redis) and `fakeredis` variant (for testing)

## Type System Support

**Serialization:**
- Native types optimized for Redis:
  - `str`, `int`, `float` - Direct Redis string/numeric operations
  - `List`, `Dict` - Native Redis LIST and JSON operations
- Complex types serialized via:
  - JSON serialization (preferred for JSON-compatible types)
  - Pickle serialization (fallback for non-JSON types)
- Configuration:
  - `prefer_normal_json_dump` - Prefer JSON over pickle when possible
  - `safe_load_all` - Treat all non-Redis types as safe load

---

*Integration audit: 2026-02-05*
