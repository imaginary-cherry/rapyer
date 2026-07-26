# Technology Stack

**Analysis Date:** 2026-07-06

## Languages

**Primary:**
- Python `>=3.10, <3.14` — entire package (`rapyer/`), tests (`tests/`), and benchmarks (`benchmarks/`)

**Secondary:**
- Lua — Redis server-side scripts for atomic operations, stored under `rapyer/scripts/lua/` (e.g. `rapyer/scripts/lua/numeric/`, `rapyer/scripts/lua/dict/`, `rapyer/scripts/lua/atomic/`, `rapyer/scripts/lua/sf/`) and loaded via `rapyer/scripts/loader.py`. Packaged into the wheel via `include = ["rapyer/**/*.lua"]` in `pyproject.toml`.

## Runtime

**Environment:**
- CPython 3.10 – 3.13 (`pyproject.toml` `requires-python = ">=3.10,<3.14"`)
- Async-first: the public API (`rapyer/init.py`, `rapyer/base.py`) is built on `asyncio` using `redis.asyncio.Redis`

**Package Manager:**
- `uv` (astral-sh) — lockfile committed at `uv.lock` (164KB, pinned resolved versions)
- Build backend: `hatchling` (`[build-system]` in `pyproject.toml`)
- CI installs deps with `uv sync --locked --group dev` (see `.github/workflows/ci.yml`)
- `tox` + `tox-gh-actions` orchestrates the actual multi-version test matrix (`tox.ini`), invoked from CI instead of `uv` directly for the test job

## Frameworks

**Core:**
- Pydantic v2 (`pydantic>=2.11.0, <2.14.0`, locked at `2.12.5`) — all Rapyer models subclass Pydantic `BaseModel`; `rapyer/config.py`'s `RedisConfig` is itself a Pydantic model
- `redis-py` (`redis>=6.0.0, <7.5.0`, locked at `7.0.1`) — official Redis client, used exclusively via its `asyncio` interface (`redis.asyncio.Redis`, `redis.asyncio.client.Pipeline`, `redis.commands.json.JSON`)

**Testing:**
- `pytest` (`>=8.4.2`, locked `9.0.2`) with `pytest-asyncio` (`>=0.25.0`, locked `1.3.0`) for async test support
- `pytest-cov` (`>=6.0.0`, locked `7.0.0`) for coverage
- `fakeredis[lua,json]` (`>=2.20.0`, locked `2.34.1`) — in-memory Redis substitute used for most unit tests (Lua + JSON extras enabled to emulate scripting and RedisJSON)
- Benchmark-only group: `pytest-benchmark` (locked `5.2.3`), `pytest-codspeed` (locked `4.3.0`) — see `[dependency-groups].benchmark` in `pyproject.toml` and `benchmarks/`

**Build/Dev:**
- `black` (dev group, locked `26.3.1`) — formatting, enforced via `tox -e lint` and CI `lint` job
- `ruff` (dev group, locked `0.15.4`) — import ordering / unused-import lint only (`[tool.ruff.lint] select = ["I", "F401"]`)
- `mypy` (dev group, locked `1.19.1`) — type checking via `tox -e mypy`, run per-Python-version in CI, scoped to `tests/models` with `--follow-imports=skip --disable-error-code=valid-type`
- `bandit` — security linter, config in `[tool.bandit]` of `pyproject.toml` (excludes `tests/`, skips `B101`)

## Key Dependencies

**Critical:**
- `redis` (`redis.asyncio`) — the only datastore client; all persistence, indexing, and Lua scripting go through it
- `pydantic` — model definition, validation, and serialization layer that Rapyer wraps with Redis persistence semantics

**Infrastructure:**
- `fakeredis` — test-only in-memory Redis emulator; `rapyer/init.py`'s `is_fakeredis()` detects it at runtime (checks `"fakeredis" in type(client).__module__`) and `rapyer/config.py`'s `is_fake_redis` flag adjusts JSON-normalization behavior for it
- `mkdocs` + `mkdocs-material` — documentation site generator (not a runtime dependency; installed ad hoc in `.github/workflows/docs.yml`, not present in `pyproject.toml`/`uv.lock`)

## Configuration

**Environment:**
- `REDIS_DB` — used by test/benchmark suites and CI to select which Redis logical DB to run against (`benchmarks/conftest.py:21`, `tox.ini` `passenv = REDIS_DB`)
- No `.env` file present in the repo; connection strings are passed programmatically to `init_rapyer()` (`rapyer/init.py`) or default to `DEFAULT_CONNECTION = "redis://localhost:6379/0"` in `rapyer/config.py`
- Secrets used only in CI (GitHub Actions `secrets.*`): `GITHUB_TOKEN`, `CODECOV_TOKEN`, `CODSPEED_TOKEN`, `GITLEAKS_LICENSE` — none required for local development

**Build:**
- `pyproject.toml` — single source of truth for package metadata, dependencies, dependency groups (`dev`, `benchmark`), and tool configuration (`ruff`, `bandit`, `pytest`, `coverage`)
- `tox.ini` — defines the full cross-version test matrix (Python 3.10–3.13 × Redis 6.0–7.4 × Pydantic 2.11–2.13) plus `lint`, `mypy`, and `coverage` environments
- `mkdocs.yml` — documentation site config (Material theme, nav structure, plugins)

## Platform Requirements

**Development:**
- Python 3.10+ interpreter, `uv` for dependency management, Docker (for running a local Redis Stack instance) or `fakeredis` for tests
- A Redis server with the JSON module (RedisJSON) is required for any real (non-fake) usage — see `docs/installation.md`

**Production:**
- Any Redis deployment that supports RedisJSON and RediSearch modules (i.e. Redis Stack, or vanilla Redis + `redis-modules`, or a managed service like AWS ElastiCache with RedisJSON support) — required because `rapyer/base.py`'s `acreate_index()` calls `redis.ft(...).create_index(..., index_type=IndexType.JSON)` and reads/writes go through `redis.json()` (RedisJSON commands)
- No application server framework is bundled — `rapyer` is a library (ORM), consumed by a host application

---

*Stack analysis: 2026-07-06*
