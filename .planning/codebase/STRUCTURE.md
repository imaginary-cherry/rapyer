# Codebase Structure

**Analysis Date:** 2026-07-06

## Directory Layout

```
rapyer/                          # PyPI package root (repo root == package repo)
├── rapyer/                      # The `rapyer` library source (installed package)
│   ├── __init__.py               # Public API surface
│   ├── base.py                   # AtomicRedisModel + module-level free functions (biggest file, ~1330 lines)
│   ├── actions.py                # ActionGroup / mark_actions TTL-refresh system
│   ├── config.py                 # RedisConfig (`Meta`)
│   ├── context.py                # contextvars-based active-pipeline plumbing
│   ├── init.py                   # init_rapyer() / teardown_rapyer()
│   ├── links.py                  # Doc-link constants used in error messages
│   ├── result.py                 # DeleteResult / GetOrCreateResult / RapyerDeleteResult
│   ├── typing_support.py         # Self/Unpack typing shims for Python 3.10 compat
│   ├── errors/                   # Exception hierarchy
│   │   ├── __init__.py            # Re-exports + deprecated-alias shim
│   │   ├── base.py                # RapyerError + most concrete errors
│   │   ├── delete.py              # BadDeleteActionError
│   │   └── find.py                # Query/index/serialization errors
│   ├── fields/                   # Annotation DSL + filter expression tree
│   │   ├── __init__.py
│   │   ├── key.py                 # Key[...] / KeyAnnotation / RapyerKey
│   │   ├── index.py               # Index[...] / IndexAnnotation
│   │   ├── safe_load.py           # SafeLoad[...] / SafeLoadAnnotation
│   │   └── expression.py          # Expression tree for afind(...) filters
│   ├── types/                    # All Redis-aware field type implementations
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseRedisType, RedisType (inline types base)
│   │   ├── special.py              # SpecialFieldType (own-key SF base)
│   │   ├── relational.py           # RelationalFieldType (FK base) + resolve_relational_targets
│   │   ├── convert.py              # RedisConverter — builds per-field dynamic subclasses
│   │   ├── generic.py              # Generic/container type handling
│   │   ├── init.py                 # ALL_TYPES: plain-type -> RedisType mapping
│   │   ├── integer.py / float.py / string.py / byte.py   # Inline scalar types
│   │   ├── dct.py / lst.py         # Inline mutable container types (dict/list)
│   │   ├── datetime.py             # RedisDatetime / RedisDatetimeTimestamp
│   │   ├── redis_set.py            # RedisSet — special field, backed by Redis SET
│   │   ├── priority_queue.py       # RedisPriorityQueue — special field, backed by Redis ZSET
│   │   └── foreign_key.py          # ForeignKey[T] — relational field
│   ├── scripts/                  # Lua script loading/registration/invocation
│   │   ├── __init__.py
│   │   ├── constants.py            # Script name constants + REDIS_VARIANT/FAKEREDIS_VARIANT
│   │   ├── loader.py               # Template loading, variant placeholder substitution
│   │   ├── registry.py             # SCRIPT_REGISTRY, register_scripts, arun_sha, NOSCRIPT retry
│   │   └── lua/                    # Lua script bodies, grouped by category
│   │       ├── atomic/get_or_create.lua
│   │       ├── numeric/{mul,floordiv,mod,pow,pow_float,truediv}.lua
│   │       ├── string/{append,mul}.lua
│   │       ├── list/remove_range.lua
│   │       ├── dict/{pop,popitem}.lua
│   │       ├── datetime/add.lua
│   │       └── sf/                 # Special-field save/load snippets, one dir per SF type
│   │           ├── redis_set/{save,load}.lua
│   │           └── redis_priority_queue/{save,load}.lua
│   └── utils/                    # Small stateless helpers
│       ├── __init__.py
│       ├── annotation.py           # TypeConverter protocol, annotation rewriting helpers
│       ├── fields.py               # Pydantic annotation collection, JSON-serializability probe
│       ├── pythonic.py             # safe_issubclass, inject_at_paths
│       └── redis.py                # Pipeline-based load/delete/scan helper functions
├── tests/                        # pytest suite (`testpaths = ["tests"]` in pyproject.toml)
│   ├── conftest.py, action_groups.py, build_helpers.py, coverage_helpers.py  # shared fixtures/helpers
│   ├── models/                    # Shared test-only AtomicRedisModel definitions, grouped by concern
│   │   (simple_types.py, collection_types.py, complex_types.py, foreign_key_types.py,
│   │    generic_types.py, index_types.py, inheritance_types.py, pickle_types.py,
│   │    pipeline_base.py, redis_types.py, safe_load_types.py, special_types.py, ...)
│   ├── unit/                      # Pure-Python / no-real-Redis unit tests, mirrors `rapyer/` shape
│   │   ├── fields/, functioninality/, mark_actions/, models/, pipeline/, types/
│   └── integration/               # Tests against a real/fake Redis instance
│       ├── actions/, dct/, fields/, foreign_keys/, functioninality/, lst/,
│       │   models/, pipeline/, simple_types/, special_types/, unknown_types/, utils/
│       └── conftest.py            # Integration-level fixtures (Redis/fakeredis setup)
├── benchmarks/                   # pytest-benchmark / pytest-codspeed performance suite
│   ├── conftest.py, base.py, models.py
│   └── test_*.py                  # One file per benchmarked feature (dict, list, numeric,
│                                    foreign_key, get_or_create, pipeline, priority_queue,
│                                    redis_set, module_api, no_redis_actions, setup)
├── docs/                         # mkdocs (Material theme) documentation source
│   ├── index.md, installation.md, changelog.md
│   ├── api/                       # Per-abstraction API reference pages
│   └── documentation/             # Conceptual guides (CRUD, atomic actions, indexing, ...)
│       └── special-fields/         # Foreign keys / priority queue / redis-set guides
├── .github/                      # CI workflows + composite actions (e.g. mirror-redis)
├── pyproject.toml                # Package metadata, dependencies, ruff/pytest/coverage config
├── tox.ini                       # Cross Python/redis/pydantic version test matrix
├── mkdocs.yml                    # Docs site config
└── CHANGELOG.md, README.md
```

## Directory Purposes

**`rapyer/`:**
- Purpose: The entire installable library. Flat-ish package with a handful of focused subpackages; no `src/` layout wrapper (declared via `[tool.hatch.build.targets.wheel] packages = ["rapyer"]`).
- Contains: Python modules + `.lua` script resources (packaged via `include = ["rapyer/**/*.lua"]`).
- Key files: `rapyer/base.py` (core model + CRUD), `rapyer/init.py` (bootstrap), `rapyer/__init__.py` (public API).

**`rapyer/types/`:**
- Purpose: Every concrete Redis-aware field type and the machinery that converts plain annotations into them.
- Contains: One module per scalar/container type, plus the three abstract bases (`base.py`, `special.py`, `relational.py`) and the conversion engine (`convert.py`).
- Key files: `rapyer/types/base.py`, `rapyer/types/convert.py`, `rapyer/types/init.py` (`ALL_TYPES` — the default `Meta.redis_type` mapping).

**`rapyer/scripts/`:**
- Purpose: Isolate all Lua-script concerns (loading from package resources, Redis/fakeredis variant differences, SHA caching, NOSCRIPT recovery) from the Python domain logic that invokes them.
- Contains: `registry.py`/`loader.py`/`constants.py` plus the `lua/` script-body tree.
- Key files: `rapyer/scripts/registry.py` (script names ↔ Lua files mapping via `SCRIPT_REGISTRY`), `rapyer/scripts/lua/atomic/get_or_create.lua` (the flagship atomic script).

**`rapyer/fields/`:**
- Purpose: User-facing field annotation markers (`Key`, `Index`, `SafeLoad`) plus the internal expression tree used to build RediSearch filter strings for `afind`.
- Contains: One module per annotation type + `expression.py`.

**`rapyer/errors/`:**
- Purpose: Centralize every exception type raised by the library under a single `RapyerError` root, split by concern (`base.py` general, `find.py` query/serialization, `delete.py` delete-specific).

**`rapyer/utils/`:**
- Purpose: Generic, stateless helper functions with no domain knowledge of models/Redis semantics beyond what's needed by callers in `base.py`/`types/`.

**`tests/models/`:**
- Purpose: Shared library of `AtomicRedisModel` subclasses used across unit + integration tests, organized by the kind of type/feature they exercise (not by which test file uses them) so multiple test modules can import the same fixture models.
- Generated: No. Committed: Yes.

**`tests/unit/`:**
- Purpose: Fast tests that avoid a real/fake Redis round trip where possible (pure logic: field conversion, action marking, expression building). Mirrors the `rapyer/` package shape (`fields/`, `models/`, `pipeline/`, `types/`) plus a dedicated `mark_actions/` and `functioninality/` (sic) directory.
- Contains: `test_*.py` files.

**`tests/integration/`:**
- Purpose: Tests that exercise real Redis/RedisJSON/RediSearch semantics (via fakeredis or a live Redis in CI), organized by feature area (`actions/`, `dct/`, `lst/`, `foreign_keys/`, `pipeline/`, `special_types/`, `unknown_types/`, `simple_types/`, `functioninality/`).
- Contains: `conftest.py` sets up the Redis/fakeredis client fixture used across the tree; `actions/` holds shared non-`test_`-prefixed helper modules (`base.py`, `create.py`, `read.py`, `update.py`, `ttl.py`, `comprehensive.py`, `two_model_delete.py`, `async_action.py`, `sync_action.py`) consumed by the actual `test_*.py` files (search siblings for exact names before assuming a 1:1 file mapping).

**`benchmarks/`:**
- Purpose: Performance regression suite using `pytest-benchmark`/`pytest-codspeed` (separate `dependency-groups.benchmark` in `pyproject.toml`, not part of the default `test` extra).
- Contains: `test_*.py` per feature area (dict, list, numeric, foreign_key, get_or_create, pipeline, pipeline_multi_model, priority_queue, redis_set, module_api, no_redis_actions, setup), plus `base.py`/`models.py`/`conftest.py` shared fixtures.
- Generated: No. Committed: Yes. Referenced images of benchmark results live in `docs/images/`.

**`docs/`:**
- Purpose: mkdocs-material documentation site source, published via GitHub Pages (`Homepage`/`Documentation` URLs in `pyproject.toml` point to `imaginary-cherry.github.io/rapyer`).
- Contains: `api/` (reference docs, one page per major abstraction — mirrors the concepts in `ARCHITECTURE.md`), `documentation/` (conceptual/how-to guides), `documentation/special-fields/` (FK/priority-queue/redis-set guides), `images/` (benchmark charts), `overrides/` (mkdocs-material theme overrides).
- Generated: `docs/changelog.md` is likely synced from `CHANGELOG.md` (check `mkdocs.yml` build hooks before assuming manual edits are safe). Committed: Yes.

## Key File Locations

**Entry Points:**
- `rapyer/__init__.py`: Public package API (import surface).
- `rapyer/init.py`: `init_rapyer()`/`teardown_rapyer()` — call once per process/app to wire models to a Redis client.

**Configuration:**
- `rapyer/config.py`: `RedisConfig` — the `Meta` class every model exposes (`redis`, `ttl`, `refresh_ttl`, `safe_load_all`, `prefer_normal_json_dump`, `max_delete_per_transaction`, `redis_type`).
- `pyproject.toml`: Package metadata, dependency ranges, ruff/pytest/coverage settings.
- `tox.ini`: Cross-version (`py310-py313` × `redis6.0-7.4` × `pydantic2.11-2.13`) test matrix.

**Core Logic:**
- `rapyer/base.py`: `AtomicRedisModel` and all CRUD/index/TTL/delete logic.
- `rapyer/actions.py`: TTL-refresh action-group system.
- `rapyer/types/convert.py`: The annotation-rewriting engine that turns plain Python types into Redis-aware ones.
- `rapyer/scripts/registry.py` + `rapyer/scripts/lua/`: Atomicity via server-side Lua.

**Testing:**
- `tests/conftest.py`, `tests/integration/conftest.py`, `tests/integration/functioninality/conftest.py`, `tests/integration/foreign_keys/conftest.py`: fixture roots at increasing specificity.
- `tests/models/`: shared model fixtures reused across unit + integration suites.
- `pyproject.toml` `[tool.pytest.ini_options]`: `testpaths = ["tests"]`.
- `pyproject.toml` `[tool.coverage.run]`: `source = ["rapyer"]`, excludes `tests/`.

## Naming Conventions

**Files:**
- Test files: `test_<feature_under_test>.py` (e.g. `test_rapyer_aget.py`, `test_find_with_expressions.py`) — snake_case, prefixed `test_`.
- Non-test helper modules inside test directories are *not* prefixed `test_` (e.g. `tests/integration/actions/base.py`, `create.py`, `read.py`, `update.py`) — pytest only collects `test_*` files, so these are safe to import as plain modules.
- Library modules: singular, lower_snake_case, named after the concept they implement (`base.py`, `actions.py`, `context.py`, `foreign_key.py`, `priority_queue.py`).
- Lua scripts: lower_snake_case matching the operation name (`floordiv.lua`, `remove_range.lua`, `get_or_create.lua`); special-field scripts always named exactly `save.lua`/`load.lua` inside a directory named after the SF type's `LUA_SNIPPET_DIR` (e.g. `sf/redis_set/save.lua`).

**Directories:**
- One directory per architectural concern under `rapyer/` (`types/`, `fields/`, `errors/`, `scripts/`, `utils/`) — flat within each, no deep nesting except `scripts/lua/` which nests by script category and then (for special fields) by type name.
- Test directories mirror feature areas, not 1:1 with `rapyer/` module names (e.g. `tests/integration/dct/` tests `rapyer/types/dct.py`, `tests/integration/lst/` tests `rapyer/types/lst.py`, but `tests/integration/functioninality/` [sic — note the codebase's existing misspelling, replicate it exactly when adding files there] covers cross-cutting CRUD/model-level behavior spanning many `rapyer/` modules).

**Classes/identifiers (for context, informs where new code should look):**
- Async persistence methods are prefixed `a` (`aget`, `asave`, `aupdate`, `adelete`, `afind`, `apush`, `apop`, `aclear`) — this prefix convention is load-bearing: `mark_actions`/`install_marked_action_methods` only wraps methods that are coroutine functions, and the `a`-prefix is the project-wide signal "this touches Redis."
- Abstract/base type names end in the role they play: `*Type` (`BaseRedisType`, `RedisType`, `SpecialFieldType`, `RelationalFieldType`); concrete Redis-backed types are prefixed `Redis*` (`RedisInt`, `RedisSet`, `RedisDict`, `RedisPriorityQueue`).
- Annotation markers use `PascalCase` factory-style names used as `Key[...]`/`Index[...]`/`SafeLoad[...]` generics, backed by a frozen dataclass `*Annotation` (`KeyAnnotation`, `IndexAnnotation`, `SafeLoadAnnotation`).

## Where to Add New Code

**New inline scalar/container Redis type:**
- Implementation: new module in `rapyer/types/` (e.g. `rapyer/types/myscalar.py`) subclassing `RedisType` (see `rapyer/types/integer.py` for the minimal shape); register the plain-type → Redis-type mapping in `rapyer/types/init.py` `ALL_TYPES`.
- Tests: add fixture models to `tests/models/simple_types.py` or `collection_types.py`; unit tests under `tests/unit/types/`; integration round-trip tests under `tests/integration/simple_types/` or a new subdirectory matching the type's name.

**New special field type (own Redis key, e.g. a new collection structure):**
- Implementation: new module in `rapyer/types/` subclassing `SpecialFieldType` (see `rapyer/types/redis_set.py` / `rapyer/types/priority_queue.py`), set `LUA_SNIPPET_DIR`, implement `asave_special`/`adelete_special`/`aduplicate_special`.
- Lua: add `rapyer/scripts/lua/sf/<type_dir>/save.lua` and `load.lua` (the `get_or_create` atomic script picks these up automatically via `SpecialFieldType.__subclasses__()` — no registry edit needed for the SF dispatch table itself).
- Tests: `tests/models/special_types.py` for fixture models; `tests/integration/special_types/` for behavior; `benchmarks/test_<type>.py` if performance-sensitive.
- Docs: add a page under `docs/documentation/special-fields/` and an entry under `docs/api/`.

**New atomic (Lua-backed) operation on an existing type:**
- Implementation: add the `.lua` file under the right `rapyer/scripts/lua/<category>/` directory, add its script-name constant to `rapyer/scripts/constants.py`, register it in `SCRIPT_REGISTRY` in `rapyer/scripts/registry.py`, then call it via `scripts_registry.run_sha`/`arun_sha` from the owning type's method in `rapyer/types/`.
- Tests: `tests/unit/` for the Python-side wiring, `tests/integration/` for the actual Redis round-trip; consider `benchmarks/` if it's a hot path.

**New relational/foreign-key-like field:**
- Implementation: subclass `RelationalFieldType` in `rapyer/types/` (see `rapyer/types/foreign_key.py`); wire target resolution through `resolve_relational_targets` in `rapyer/types/relational.py` if it needs deferred-target semantics like `ForeignKey`.
- Tests: `tests/models/foreign_key_types.py`, `tests/integration/foreign_keys/`.

**New CRUD/query capability on `AtomicRedisModel`:**
- Implementation: add the method to `rapyer/base.py`, decorate with `@mark_actions(...)` choosing the right `ActionGroup`(s) and `TargetSource`; if it's also exposed as a module-level free function, mirror it near the bottom of `rapyer/base.py` (see `aget`/`afind`/`ainsert`/`adelete_many` module-level wrappers) and re-export from `rapyer/__init__.py`.
- Tests: `tests/unit/functioninality/` and/or `tests/integration/functioninality/` (note the existing misspelling — match it) plus `tests/unit/mark_actions/` if the action-group/TTL interaction needs dedicated coverage.

**New exception type:**
- Implementation: add to `rapyer/errors/base.py` (general) or `rapyer/errors/find.py`/`delete.py` (topic-specific) subclassing `RapyerError`; re-export from `rapyer/errors/__init__.py` and add to its `__all__`.

**New annotation marker (like `Key`/`Index`/`SafeLoad`):**
- Implementation: new module in `rapyer/fields/` following the `_XxxType`/`XxxAnnotation` pattern in `rapyer/fields/key.py` or `rapyer/fields/index.py`; wire detection into `AtomicRedisModel.__init_subclass__` in `rapyer/base.py` (search for `has_annotation(annotation, KeyAnnotation)` for the pattern to replicate).

## Special Directories

**`rapyer/scripts/lua/`:**
- Purpose: Non-Python source shipped inside the wheel (`include = ["rapyer/**/*.lua"]` in `pyproject.toml`), loaded at runtime via `importlib.resources`.
- Generated: No — hand-written Lua, version-controlled like any source file.
- Committed: Yes.

**`.planning/`:**
- Purpose: GSD workflow planning artifacts (this document's own output location: `.planning/codebase/`).
- Generated: Yes, by GSD tooling (`/gsd:map-codebase` and related commands).
- Committed: Check `.gitignore` before assuming — treat as tooling-managed, not hand-edited.

**`docs/images/`:**
- Purpose: Pre-rendered benchmark result charts (`adelete_many_performance.png`, `afind_performance.png`, `ainsert_performance.png`) referenced from documentation pages.
- Generated: Likely produced from `benchmarks/` runs (regenerate manually when benchmark results change materially — no automated regeneration hook found in this pass).
- Committed: Yes.

---

*Structure analysis: 2026-07-06*
