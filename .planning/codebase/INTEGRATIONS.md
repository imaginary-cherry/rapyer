# External Integrations

**Analysis Date:** 2026-07-06

## APIs & External Services

**Datastore (the only runtime dependency):**
- Redis (with RedisJSON + RediSearch modules, i.e. "Redis Stack") — the sole backend; Rapyer is an ORM that maps Pydantic models onto Redis keys
  - Client: `redis.asyncio.Redis` from `redis-py` (see `rapyer/config.py`, `rapyer/init.py`)
  - Auth/connection: connection URL or a live `Redis` instance passed to `init_rapyer()` (`rapyer/init.py`); default `DEFAULT_CONNECTION = "redis://localhost:6379/0"` in `rapyer/config.py`
  - Modules required: **RedisJSON** (`redis.commands.json.JSON`, used for `JSON.SET`/`JSON.GET` style document storage — see `rapyer/base.py:211`, `:587`, `:611`) and **RediSearch** (`redis.ft(...)` index creation/drop for indexed fields — `rapyer/base.py:281-295`)
  - Server-side Lua scripting: custom scripts are `SCRIPT LOAD`-ed at `init_rapyer()` time and invoked via `EVALSHA` for atomic numeric/dict/string/datetime operations and atomic get-or-create (`rapyer/scripts/registry.py`, script sources under `rapyer/scripts/lua/`)
  - Test-time substitute: `fakeredis` (`fakeredis[lua,json]`) emulates this whole surface in-memory; `rapyer/init.py`'s `is_fakeredis()` and `RedisConfig.is_fake_redis` (`rapyer/config.py`) branch behavior where fakeredis diverges from real Redis (see `FAKEREDIS_VARIANT` vs `REDIS_VARIANT` script templates in `rapyer/scripts/loader.py`)

**No other external APIs.** No HTTP clients, third-party SaaS SDKs (payments, email, cloud storage, etc.) appear anywhere in `rapyer/`.

## Data Storage

**Databases:**
- Redis (with JSON + Search modules) is the only persistence layer
  - Connection: passed to `init_rapyer(redis: str | Redis, ...)` — either a connection string or a pre-built `redis.asyncio.Redis` client
  - Client/ORM layer: `rapyer/base.py` (model base class with CRUD + indexing), `rapyer/config.py` (`RedisConfig`), `rapyer/context.py` (pipeline/transaction context management)
  - Logical DB selection in dev/test/CI via `REDIS_DB` env var (`benchmarks/conftest.py:21`, `tox.ini`)

**File Storage:**
- Local filesystem only — Lua script templates are packaged and read via `importlib.resources` (`rapyer/scripts/loader.py`); no blob/object storage integration

**Caching:**
- None separate from Redis itself (Redis is both the store and, incidentally, usable as a cache by the consuming application via `ttl`/`refresh_ttl` config in `RedisConfig`)

## Authentication & Identity

**Auth Provider:**
- None built into the library. Redis auth (if any) is the responsibility of the connection string/`Redis` client the host application supplies to `init_rapyer()`.

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry/Rollbar/etc. integration)

**Logs:**
- Standard library `logging` — `init_rapyer(..., logger: logging.Logger = None)` in `rapyer/init.py` optionally attaches a caller-supplied logger's handlers/level to the `"rapyer"` logger namespace

## CI/CD & Deployment

**Hosting:**
- PyPI (package distribution) — published via GitHub Actions trusted publishing, no API tokens stored
- GitHub Pages (documentation site) — built with MkDocs Material and deployed via `actions/deploy-pages`

**CI Pipeline (GitHub Actions, all under `.github/workflows/`):**
- `ci.yml` — main pipeline: branch-target validation, Redis image mirroring (see below), `ruff`/`black` lint job, `mypy` job (matrix over Python 3.10–3.13), and the full test matrix (Python × Redis × Pydantic versions) run through `tox`
- `coverage.yml` — runs `tox -e coverage` against a live Redis service container, posts a coverage summary as a PR comment (`.github/scripts/comment_coverage.sh`) and uploads results to **Codecov** (`codecov/codecov-action@v5`, gated to `main` via a restricted `coverage` GitHub environment, requires `CODECOV_TOKEN` secret); config in `codecov.yml`
- `docs.yml` — builds and deploys the MkDocs site to GitHub Pages on pushes touching `docs/**`/`mkdocs.yml`/README, and regenerates `docs/roadmap.md` from GitHub Issues via `.github/scripts/generate_roadmap.py` (uses `GITHUB_TOKEN` + GitHub REST/GraphQL API)
- `publish.yml` — on successful CI run on `main`, builds with `uv build` and publishes to PyPI via `pypa/gh-action-pypi-publish` (OIDC trusted publishing, no stored PyPI token), then tags the release (`vX.Y.Z`) from `pyproject.toml`'s version
- `release.yml` — after a successful publish, creates a GitHub Release from the new tag, extracting notes from `CHANGELOG.md`
- `speed.yml` — runs performance benchmarks (`benchmarks/`) against a live `redis/redis-stack-server` container using **CodSpeed** (`CodSpeedHQ/action@v4`, requires `CODSPEED_TOKEN` secret; also configured as an MCP server in `.mcp.json` pointing at `https://mcp.codspeed.io/mcp`)
- `bandit.yml` — Bandit security-linter scan uploaded to GitHub code scanning (SARIF)
- `codeql.yml` — GitHub CodeQL analysis (Python + GitHub Actions workflows) on a weekly schedule and on push/PR
- `security.yml` — dependency vulnerability scan via `pip-audit` (against `uv export`-ed lockfile) and secret scanning via **Gitleaks** (`gitleaks/gitleaks-action@v2`, requires `GITLEAKS_LICENSE` secret)
- `semgrep.yml` — tokenless Semgrep `auto` ruleset scan, SARIF uploaded to code scanning
- `pm.yml` — project-management automation: auto-closes linked issues when a PR merges to `develop`/`main` (`ldez/gha-mjolnir`, plus a custom `actions/github-script` step parsing issue numbers from branch names)

**Container/Image infrastructure:**
- `.github/actions/mirror-redis/action.yml` — a composite action that mirrors `redis/redis-stack-server` (default tag `7.4.0-v8`) from Docker Hub into this repo's GHCR namespace once, so the CI/coverage test-matrix jobs pull the Redis service container from GHCR (avoiding Docker Hub rate limits) instead of Docker Hub directly
- `speed.yml` pulls `redis/redis-stack-server:latest` directly from Docker Hub (not mirrored) for benchmark runs

## Environment Configuration

**Required env vars (CI/test only, none required in production by the library itself):**
- `REDIS_DB` — logical Redis DB index for tests/benchmarks
- `GITHUB_TOKEN` — used across nearly every workflow (checkout auth, GHCR push/pull, PR comments, release creation, roadmap generation)
- `CODECOV_TOKEN` — coverage upload (`coverage.yml`)
- `CODSPEED_TOKEN` — benchmark upload (`speed.yml`)
- `GITLEAKS_LICENSE` — secret-scanning license (`security.yml`)

**Secrets location:**
- All secrets are GitHub Actions repository/environment secrets (`secrets.*` in workflow YAML); none are checked into the repo. No `.env` files exist in the project.

## Webhooks & Callbacks

**Incoming:**
- None in the library itself. `docs.yml` reacts to GitHub-native events (`issues`, `milestone`) to regenerate the roadmap page, but this is GitHub Actions' own event system, not a custom webhook endpoint.

**Outgoing:**
- None (no outbound webhook calls from `rapyer/`)

---

*Integration audit: 2026-07-06*
