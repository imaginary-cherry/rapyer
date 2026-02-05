# Technology Stack

**Analysis Date:** 2026-02-05

## Languages

**Primary:**
- Python 3.10, 3.11, 3.12, 3.13 - Core application language for async Redis ORM

## Runtime

**Environment:**
- Python 3.10+ (tested via tox with 3.10, 3.11, 3.12, 3.13)

**Package Manager:**
- Poetry 2.2.1 - Dependency management and build system
- Lockfile: `poetry.lock` (present, version-pinned)

## Frameworks

**Core:**
- Pydantic v2 (2.11.0-2.13.0) - Data validation, serialization, and model definitions
- pydantic-core (2.33.2) - Low-level Pydantic validation engine

**Database/Caching:**
- Redis (6.0.0-7.0.0) - Primary data storage backend via `redis-py` async client
  - `redis[async]` package - Async Redis client with asyncio support
  - Supports Redis JSON module for optimized JSON operations
  - Lua script support for atomic operations

**Testing:**
- pytest (8.4.2-9.0.1) - Test runner and framework
- pytest-asyncio (0.25.0-1.3.0) - Async test support
- pytest-cov (6.0.0-7.0.0) - Code coverage reporting
- fakeredis[lua,json] (2.20.0-2.33.0) - In-memory Redis mock for testing

**Code Quality:**
- Black (25.9.0) - Code formatting and style enforcement
- mypy (1.0.0-1.18.2) - Static type checking
- Bandit - Security linting

**Build/Dev:**
- tox - Multi-environment testing orchestration
- coverage - Code coverage measurement
- pytest plugins for async test support

## Key Dependencies

**Critical:**
- `redis[async]>=6.0.0, <7.1.0` - Primary Redis client, must be async-enabled
- `pydantic>=2.11.0, <2.13.0` - Type validation and data modeling
- `pydantic-core` (transitively) - Validation engine

**Testing/Development:**
- `fakeredis[lua,json]>=2.20.0` - Required for unit tests (no external Redis needed)
- `pytest>=8.4.2` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting

**Infrastructure:**
- `async-timeout` (5.0.1) - Timeout management for async operations
- `annotated-types` (0.7.0) - Type annotation support for Pydantic
- `lupa` (2.6) - Lua environment for FakeRedis Lua script support
- `jsonpath-ng` (1.7.0) - JSON path queries for FakeRedis

## Configuration

**Environment:**
- No `.env` file requirement detected
- Configuration via Python dataclass: `RedisConfig` in `rapyer/config.py`
- Default Redis connection: `redis://localhost:6379/0`

**Build:**
- `pyproject.toml` - Project metadata, dependencies, tool configuration
- `tox.ini` - Test environment matrix configuration
- `poetry.toml` - Poetry configuration
- `.github/workflows/` - CI/CD configuration (GitHub Actions)

**Code Quality Configuration:**
- `[tool.coverage.run]` - Coverage source: `rapyer` package
- `[tool.bandit]` - Security checks configured (skips B101: assert_used in tests)
- Black formatting enforced via tox lint environment

## Platform Requirements

**Development:**
- Python 3.10+
- Redis server (6.0+) with JSON module for local testing
- Or use FakeRedis for unit tests (no external Redis needed)
- Poetry for dependency management

**Production:**
- Python 3.10+ runtime
- Redis server (6.0+) with JSON module
- Network access to Redis instance

**Tested Environments (via tox matrix):**
- Python: 3.10, 3.11, 3.12, 3.13
- Redis versions: 6.0, 6.1, 6.2, 6.3, 6.4
- Pydantic versions: 2.11.x, 2.12.x

---

*Stack analysis: 2026-02-05*
