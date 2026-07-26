# Testing Patterns

**Analysis Date:** 2026-07-06

## Test Framework

**Runner:**
- `pytest` >= 8.4.2, configured via `[tool.pytest.ini_options]` in `pyproject.toml`: `testpaths = ["tests"]` (benchmarks live outside `testpaths` and are run explicitly — see Benchmarks section).
- `pytest-asyncio` >= 0.25.0 — **no `asyncio_mode` is set** anywhere (checked `pyproject.toml`, no `pytest.ini`/`setup.cfg`), so the default **strict mode** applies: every async test function must be explicitly decorated with `@pytest.mark.asyncio`. There is no blanket auto-mode; forgetting the marker means the test silently doesn't run as a coroutine.
- `pytest-cov` >= 6.0.0 for coverage collection.
- `fakeredis[lua,json]` >= 2.20.0 provides the in-memory Redis used by unit tests (see Redis Mocking below).

**Custom plugins (project-local, not pip packages):**
- `tests/conftest.py` implements a **custom pytest plugin** for "action coverage" — a project-specific enforcement layer, not a generic testing tool. It defines `pytest_addoption` (adds `--action-coverage` flag), `pytest_configure` (registers dynamic markers per `CoverageCheck`), `pytest_runtest_makereport` (accumulates which `(class, method)` tuples were exercised by test markers), and `pytest_sessionfinish` (fails the run if any expected Redis-touching method lacks a covering test). This is root-level so it applies to both `tests/unit/` and `tests/integration/`.

**Run Commands:**
```bash
pytest                                  # Run all tests (from testpaths = tests)
pytest --action-coverage                # Also enforce the custom action-coverage matrix (used by CI via tox)
pytest tests/unit                       # Unit tests only (fakeredis, no external services)
pytest tests/integration                # Integration tests only (requires real Redis on localhost:6370)
tox -e coverage                         # pytest --cov=rapyer --cov-report=xml --cov-report=html --cov-report=term
tox                                     # Full matrix: py{310..313} x redis{6.0..7.4} x pydantic{2.11..2.13} + lint + mypy
uv run pytest benchmarks/ --codspeed    # Benchmarks (see Benchmarks section)
```

## Test File Organization

**Location:** `tests/` is split into two top-level suites plus shared fixture/model modules:
```
tests/
├── conftest.py              # root: action-coverage plugin (see above)
├── action_groups.py         # PRIVATE_METHODS / NON_ACTION_METHODS registries used by the coverage plugin
├── build_helpers.py         # recursive_build_redis_model() — rebuilds a model + nested Redis types against a Meta
├── coverage_helpers.py      # COVER_* marker name constants, cover_tuple(), all_subclasses(), should_ignore_group()
├── models/                  # shared Pydantic/AtomicRedisModel fixtures used by BOTH unit and integration tests
│   ├── simple_types.py, collection_types.py, complex_types.py, foreign_key_types.py,
│   │   functionality_types.py, generic_types.py, index_types.py, inheritance_types.py,
│   │   pickle_types.py, redis_types.py, safe_load_types.py, special_types.py,
│   │   specialized.py, unit_types.py, unknown_types.py, pipeline_base.py, common.py
│   └── registry.py          # TESTED_REDIS_MODELS — the master list integration conftest configures per-test
├── unit/                    # fakeredis-backed, no network required
│   ├── conftest.py          # fake_redis_client, restore_redis_models, clean_redis_models fixtures
│   ├── assertions.py        # assert_redis_dict_item_correct / assert_redis_list_* helpers (pytest.register_assert_rewrite'd)
│   ├── fields/, functioninality/, mark_actions/, models/, pipeline/, types/
│   └── test_*.py            # flat top-level unit tests (action_groups, base_functions, model_config, scripts, ...)
└── integration/             # real-Redis-backed (redis/redis-stack-server via docker-compose or CI service)
    ├── conftest.py          # redis_client / real_redis_client fixtures, TTL fixtures
    ├── docker-compose.redis.yml  # local Redis-stack container definition (port 6370)
    ├── actions/              # the ActionTestBase framework (base.py, read.py, update.py, ttl.py, sync_action.py, async_action.py)
    │   └── redis_types/       # per-type ActionTestBase subclasses (test_set.py, ...)
    ├── dct/, lst/, fields/, models/, pipeline/, special_types/, functioninality/, foreign_keys/, simple_types/, unknown_types/, utils/
    └── test_*.py             # flat top-level integration tests (index_creation, ttl, none_values, init_rapyer, ...)
```

**Naming:** `test_<subject>.py` files; test functions `test_<behavior>`; test classes (when used) `Test<Subject>` grouping related parametrized cases under one shared fixture/name (e.g. `TestRedisModelDictOperations` in `tests/unit/models/test_redis_model_operations.py`).

**Project convention (per `.coderabbit.yaml` `path_instructions` for `tests/**`):** default to **plain test functions, not classes**, for ordinary test cases. Classes are reserved for the deliberate shared-behavior frameworks (`ActionTestBase` and its mixins in `tests/integration/actions/`, `AsyncBenchmarkTest` in `benchmarks/base.py`) where inheritance drives auto-generated, parametrized, marker-tagged test methods via `__init_subclass__` — not for simple grouping.

## Test Structure

**Plain unit test — Arrange/Act/Assert with explicit comments:**
```python
@pytest.mark.parametrize(
    ["refresh_ttl", "action", "expected"],
    [
        [True, ActionGroup.READ, True],
        [False, ActionGroup.READ, False],
        [ActionGroup.READ | ActionGroup.UPDATE, ActionGroup.DELETE, False],
    ],
)
def test_should_refresh_for_action(refresh_ttl, action, expected):
    # Arrange
    config = RedisConfig(ttl=60, refresh_ttl=refresh_ttl)

    # Act
    result = should_refresh_for_action(config, action)

    # Assert
    assert result == expected
```
(`tests/unit/models/test_redis_model_operations.py`)

**Parametrize convention:** `argnames` passed as a **list of strings** (`["refresh_ttl", "action", "expected"]`, not a comma-joined string or tuple) and each parameter row as a **list** (`[True, ActionGroup.READ, True]`, not a tuple) — per `.coderabbit.yaml` review instructions for `tests/**`. Follow list-of-lists, not tuple-of-tuples, for new parametrized tests.

**Async test:**
```python
@pytest.mark.asyncio
async def test_pipeline_atomicity(self, test_input):
    # Arrange
    self.test_input = test_input
    self.created_models = await self.setup_data()

    # Act
    async with rapyer.apipeline():
        await self.perform_action(self.created_models[0])
        loaded_during = await self.load_data()
        self.assert_during_pipeline(loaded_during)

    # Assert (after pipeline)
    loaded_after = await self.load_data()
    await self.assert_after_pipeline(loaded_after)
```
(`tests/integration/actions/base.py`) — every async test needs the explicit `@pytest.mark.asyncio` marker (strict mode, no auto-detection).

**Shared-behavior test framework (`ActionTestBase`, `tests/integration/actions/base.py`):** an `ABC` with `abstractmethod`s (`create_models`, `perform_action`) and hook methods with sensible defaults (`setup_data`, `load_data`, `expected_before`/`expected_after`, `assert_during_pipeline`/`assert_after_pipeline`, `corrupt_local_mirror`). `__init_subclass__` auto-generates and parametrizes concrete test methods (`test_pipeline_atomicity`, `test_action_in_pipeline_tolerates_stale_local_mirror`, per-special-field lifecycle tests) on every concrete subclass, tagging each with a `cover_<...>` pytest marker recording which `(ClassName, method_name)` it exercises. This is how one Redis-type method (e.g. `RedisSet.aadd`) gets pipeline-atomicity, stale-mirror, TTL, and special-field-lifecycle coverage from a handful of declarative subclass attributes instead of hand-written boilerplate per behavior. New Redis-type actions should get a subclass here (see `tests/integration/actions/redis_types/test_set.py` for the canonical example) rather than ad hoc integration tests, to stay inside the action-coverage enforcement.

## Mocking

**Framework:** `unittest.mock` (`AsyncMock`, `MagicMock`, `patch`) for narrowly scoped isolation — e.g. `monkeypatch.setattr(rapyer.actions, "flush_action_targets", flush_mock)` in the `force_no_ttl_updates` fixture (`tests/conftest.py`), or `patch("rapyer.scripts.registry.handle_noscript_error", new_callable=AsyncMock)` in `disable_noscript_recovery` (`tests/integration/conftest.py`).

**What's mocked:** internal collaborator functions when a test needs to assert a code path was/wasn't taken (e.g. "TTL refresh flush was not called"), or to force an error-recovery branch (`NOSCRIPT` handling) without actually corrupting the Lua script cache.

**What's NOT mocked — the primary approach is real Redis protocol, not mocked clients:**
- **Unit tests** run against `fakeredis.aioredis.FakeRedis` (an in-process reimplementation of the Redis protocol, including Lua scripting and RedisJSON via `fakeredis[lua,json]`), not a `Mock`/`MagicMock` client. The `fake_redis_client` fixture (`tests/unit/conftest.py`) constructs it, calls `register_scripts(client, is_fakeredis=True)`, yields it, then `await client.aclose()`.
- **Integration tests** run against an actual `redis/redis-stack-server` instance (RedisJSON + RediSearch modules included) reached over the network at `localhost:6370` — see Redis Setup below.
- This means model (de)serialization, RedisJSON path operations, index creation/search, and Lua scripts are exercised against real (or protocol-faithful fake) Redis behavior rather than assumption-laden mocks.

## Fixtures and Factories

**Shared model fixtures (not per-test factories):** `tests/models/*.py` define reusable `AtomicRedisModel` subclasses (e.g. `SimpleDictModel`, `ComprehensiveTestModel`, `TTLRefreshTestModel`) that both unit and integration suites import directly — there is no factory-library (e.g. `factory_boy`) in use; models are instantiated inline with plain keyword args, e.g.:
```python
model = TTLRefreshTestModel(
    name="ttl_test", age=25, score=10.5,
    tags=["tag1", "tag2"], settings={"key1": "value1", "key2": "value2"},
)
```
(`tests/integration/conftest.py`, `saved_model_with_reduced_ttl` fixture)

**Model registry:** `tests/models/registry.py` exposes `TESTED_REDIS_MODELS`, the master list of every model class exercised by the suite; `tests/integration/conftest.py`'s `real_redis_client` fixture iterates it to point every model's `Meta.redis` at the freshly-flushed test Redis connection before each test.

**Key fixtures:**
- `tests/unit/conftest.py`: `fake_redis_client` (function-scoped fakeredis client + script registration), `restore_redis_models`/`clean_redis_models` (snapshot/restore or clear the global `REDIS_MODELS` registry so model-registration tests don't leak state), `force_no_ttl_updates` (`tests/conftest.py`, mocks TTL-flush to assert it wasn't called).
- `tests/integration/conftest.py`: `redis_client` (raw connection to `redis://localhost:6370/{REDIS_DB}`, flushed before/after), `real_redis_client` (autouse — re-resolves forward refs/relational targets, repoints every tested model's `Meta.redis`, registers Lua scripts, yields, then closes), `saved_model_with_reduced_ttl` / `saved_no_refresh_model_with_reduced_ttl` (pre-saved model with TTL forced down to `REDUCED_TTL_SECONDS = 10` for TTL-expiry assertions), `flush_scripts` (forces a Lua `SCRIPT FLUSH` to test `NOSCRIPT` recovery), `disable_noscript_recovery`.

**Assertion helpers:** `tests/unit/assertions.py` centralizes structural assertions for Redis-backed containers (`assert_redis_list_correct_types`, `assert_redis_dict_item_correct`, `assert_redis_list_item_correct`) checking type, string representation, `.key`, and `.field_path` in one call; registered with `pytest.register_assert_rewrite("tests.assertions")` (`tests/unit/conftest.py`) so `assert` failures inside these helpers get pytest's introspective rewriting.

## Coverage

**Standard coverage (line/branch, `pytest-cov`):**
- Config in `pyproject.toml`: `[tool.coverage.run] source = ["rapyer"]`, `omit = ["*/tests/*", "*/test_*"]`.
- Standard exclusions in `[tool.coverage.report]`: `pragma: no cover`, `def __repr__`, `raise AssertionError`, `raise NotImplementedError`, `if __name__ == .__main__.:`, `if TYPE_CHECKING:`.
- Requirements: **informational only** — `codecov.yml` sets `coverage.status.project.default.informational: true` and `coverage.status.patch.default.informational: true` with `target: auto`; Codecov does not block merges on coverage delta, it reports.
- Generate: `tox -e coverage` → `pytest --cov=rapyer --cov-report=xml --cov-report=html --cov-report=term`.

**Custom "action coverage" (project-specific, enforced, not from codecov):**
- Run with `pytest --action-coverage` (also how `tox`'s default `[testenv]` invokes tests: `pytest {posargs} --action-coverage`, so the full CI test matrix in `.github/workflows/ci.yml` enforces it on every push/PR).
- This is a **semantic** coverage check layered on top of line coverage: it verifies that every discovered Redis-"action" method (anything carrying an `ActionGroup` via `mark_actions`, across `AtomicRedisModel`, every `BaseRedisType` subclass, and module-level `rapyer` functions) has at least one test asserting each of several specific behavioral contracts — pipeline atomicity, TTL refresh/no-refresh/update-once, no-clobber semantics, sync-vs-native-Python parity, stale-local-mirror tolerance, special-field lifecycle — not just "was this line executed."
- Failing checks surface as **synthetic pytest test reports** (`tests/conftest.py::_emit_coverage_reports` creates `TestReport` objects at `pytest_sessionfinish` for every `(class, method)` missing a given coverage marker) so an uncovered action shows up in the pytest output exactly like a failing test, with a message telling you which `ActionTestBase` subclass/marker to add.
- Exclusion lists (`tests/action_groups.py`: `PRIVATE_METHODS`, `PRIVATE_INHERITED_METHODS`, `NON_ACTION_METHODS`, `SYNC_NATIVE_EFFECT_GROUP`, `STALE_MIRROR_GROUP`, `SYNC_NATIVE_RAISES_GROUP`) are the sanctioned way to opt a method out of a specific check, always with an inline comment explaining *why* it doesn't apply — follow that pattern (explicit exclusion + rationale comment) rather than silently skipping.

**CI coverage reporting workflow (`.github/workflows/coverage.yml`):**
1. `mirror-redis` job mirrors the `redis/redis-stack-server` image into GHCR (avoids Docker Hub rate limits), reused by both `coverage.yml` and `ci.yml`.
2. `coverage` job runs `tox -e coverage` against that Redis service (port 6370), posts a `## Coverage report` summary to the GitHub Actions job summary, comments coverage on the PR via `.github/scripts/comment_coverage.sh`, and uploads `coverage.xml` as an artifact.
3. `codecov` job (only on `main`, using a restricted `coverage` environment) downloads the artifact and uploads it to Codecov via `codecov/codecov-action@v5` using `secrets.CODECOV_TOKEN`.

## Test Types

**Unit Tests (`tests/unit/`):** fakeredis-backed; cover pure logic (action-group resolution, TTL-refresh predicate logic, field utilities, script constants, deprecation shims) and Redis-protocol-dependent behavior that doesn't require real RediSearch/Lua-persistence guarantees (e.g. `test_rapyer_afind_with_fakeredis.py`, `test_pipeline_setattr_with_fakeredis.py`).

**Integration Tests (`tests/integration/`):** real `redis/redis-stack-server` instance; cover anything depending on genuine RedisJSON path semantics, RediSearch index creation/queries, real Lua script persistence/`NOSCRIPT` recovery, TTL expiry timing, and the full `ActionTestBase` pipeline-atomicity/TTL/special-field-lifecycle matrix per Redis type.

**E2E Tests:** Not used — there is no browser/API-level end-to-end layer; the "integration" tier already exercises the full stack down to a real Redis server, which is the system's only external dependency.

**Benchmarks (`benchmarks/`, separate from `testpaths`):** performance regression tests using `pytest-benchmark` + `pytest-codspeed`, run explicitly (`pytest benchmarks/ --codspeed`), never as part of the normal `pytest`/`tox` unit+integration run. Structure:
- `benchmarks/conftest.py`: session-scoped `event_loop` and `redis_client` fixtures, plus an autouse session `real_redis_client` fixture that flushes the DB and calls `init_rapyer(redis=redis_client)` once for the whole benchmark session (contrast with integration tests, which flush and reconfigure per-test).
- `benchmarks/base.py`: `AsyncBenchmarkTest` base class — `pytestmark = [pytest.mark.benchmark]`, `rounds = 30`, `warmup_rounds = 5`. Subclasses override `setup(self, mode: TTLMode)` (build fresh per-round state) and `action(self, *args, **kwargs)` (the operation being timed); `_run()` bridges async setup/action into `benchmark.pedantic(sync_action, setup=sync_setup, rounds=..., warmup_rounds=...)` since `pytest-benchmark`/`pytest-codspeed` drive synchronous callables. `AsyncBenchmarkTestWithTTL` adds a second `test_benchmark_with_ttl` variant. `TTLMode` (`NO_TTL`/`TTL`) selects which pre-declared model class (`ClassVar[dict[TTLMode, type[AtomicRedisModel]]]`) a benchmark exercises — models are separate classes with TTL fixed at class-definition time, not mutated at runtime, to avoid install/uninstall cycles skewing timings.
- Per-feature benchmark files: `test_dict.py`, `test_list.py`, `test_numeric.py`, `test_redis_set.py`, `test_foreign_key.py`, `test_priority_queue.py`, `test_pipeline.py`, `test_pipeline_multi_model.py`, `test_get_or_create.py`, `test_model.py`, `test_module_api.py`, `test_no_redis_actions.py`, `test_setup.py`.
- CI: `.github/workflows/speed.yml` ("CodSpeed Benchmarks") runs on push to `main`/`develop`, on PRs, and on manual dispatch, using `runs-on: codspeed-macro` against a `redis/redis-stack-server` service container, uploading results via `CodSpeedHQ/action@v4` with `mode: walltime` to `secrets.CODSPEED_TOKEN`. Regressions surface in the CodSpeed dashboard/PR check, not as a hard `pytest` failure.

## Redis Setup for Tests

**Unit tests:** no external service — `fakeredis.aioredis.FakeRedis(decode_responses=True)`, purely in-process.

**Integration tests / benchmarks:** require a running `redis/redis-stack-server` (includes RedisJSON + RediSearch modules) reachable at `localhost:6370` (not the default `6379`, to avoid colliding with a local Redis):
- Local dev: `docker compose -f tests/integration/docker-compose.redis.yml up -d` (service name `redis`, image `redis/redis-stack-server:latest`, port mapping `6370:6379`, healthcheck `redis-cli ping`).
- CI: `.github/actions/mirror-redis` mirrors the same image into GHCR once per workflow run (`ci.yml`, `coverage.yml`) and starts it as a GitHub Actions `services:` container on the same `6370:6379` mapping with a matching healthcheck; `speed.yml` runs the upstream image directly as a service container instead of using the mirror action.
- The DB index is selectable via the `REDIS_DB` env var (`passenv = REDIS_DB` in `tox.ini`; CI sets `REDIS_DB: 0`), letting parallel matrix jobs avoid clobbering each other's keys if run against a shared server.

## Common Patterns

**Pipeline atomicity assertion (the core integration testing idiom):**
```python
async with rapyer.apipeline():
    await self.perform_action(self.created_models[0])
    loaded_during = await self.load_data()
    self.assert_during_pipeline(loaded_during)   # value NOT yet visible/committed

loaded_after = await self.load_data()
await self.assert_after_pipeline(loaded_after)   # value committed after pipeline exits
```

**Error/warning testing:**
```python
with pytest.raises(InvalidRefreshTtlError):
    class _BadModel(AtomicRedisModel):
        Meta = RedisConfig(ttl=60, refresh_ttl=bad_refresh_ttl)
```
```python
with pytest.warns(DeprecationWarning):
    aliased = errors.UnsupportArgumentTypeError
```
(both from `tests/unit/`)

**Registry isolation:** tests that register new `AtomicRedisModel` subclasses (e.g. to test `DuplicateModelNameError`) take the `restore_redis_models` fixture to snapshot/restore the module-level `REDIS_MODELS` list so one test's dynamically-defined class doesn't leak into subsequent tests.

---

*Testing analysis: 2026-07-06*
