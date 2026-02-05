# Codebase Structure

**Analysis Date:** 2026-02-05

## Directory Layout

```
rapyer/
├── __init__.py              # Public API exports
├── base.py                  # Core AtomicRedisModel class
├── config.py                # RedisConfig dataclass
├── context.py               # Context variable for pipeline state
├── init.py                  # init_rapyer() and teardown_rapyer()
├── typing_support.py        # Type hints (Self, Unpack)
├── errors/                  # Custom exception classes
│   ├── __init__.py
│   └── base.py             # KeyNotFound, CantSerializeRedisValueError, etc.
├── fields/                  # Query expression system
│   ├── __init__.py
│   ├── expression.py       # Expression, ExpressionField, comparison ops
│   ├── index.py            # IndexAnnotation for field indexing
│   ├── key.py              # KeyAnnotation for custom primary keys
│   └── safe_load.py        # SafeLoadAnnotation for soft deserialization
├── types/                   # Redis type wrappers
│   ├── __init__.py         # Public type exports
│   ├── base.py             # RedisType base class, GenericRedisType
│   ├── convert.py          # RedisConverter for type transformation
│   ├── byte.py             # RedisBytes class
│   ├── datetime.py         # RedisDatetime, RedisDatetimeTimestamp
│   ├── dct.py              # RedisDict class
│   ├── float.py            # RedisFloat class
│   ├── init.py             # ALL_TYPES registry
│   ├── integer.py          # RedisInt, RedisBool classes
│   ├── lst.py              # RedisList class
│   └── string.py           # RedisStr class
├── utils/                   # Utility functions
│   ├── __init__.py
│   ├── annotation.py       # Type annotation helpers
│   ├── fields.py           # Field introspection utilities
│   ├── pythonic.py         # safe_issubclass() and helpers
│   └── redis.py            # Redis command builders
├── scripts/                 # Lua script management
│   ├── __init__.py         # Script running functions
│   ├── constants.py        # Script name constants
│   ├── loader.py           # Template loading and variant substitution
│   ├── registry.py         # Script registration and caching
│   └── lua/                # Lua script templates
│       ├── __init__.py
│       ├── datetime/       # Datetime manipulation scripts
│       ├── dict/           # Dictionary operation scripts
│       ├── list/           # List operation scripts
│       ├── numeric/        # Numeric operation scripts
│       └── string/         # String operation scripts
└── links.py                # REDIS_SUPPORTED_LINK constant

tests/
├── conftest.py             # TTL test decorators
├── unit/                   # Unit tests (no Redis server required)
│   ├── conftest.py        # fake_redis_client fixture
│   ├── test_ttl_enforcement.py
│   ├── pipeline/          # Pipeline-specific tests
│   └── types/             # Type-specific tests
│       ├── simple_types/  # str, int, float, bytes, datetime
│       ├── collection_types/  # list, dict
│       └── complex_types/  # nested models, dataclasses
├── integration/            # Integration tests (requires Redis server)
│   ├── test_*.py          # Full scenario tests
│   └── ...
└── models/                 # Test models (shared across all tests)
    ├── __init__.py
    ├── *.py               # Model definitions for testing
    └── unit_types.py      # Unit test specific models
```

## Directory Purposes

**rapyer/:**
- Purpose: Main package source code
- Contains: ORM core, type wrappers, utilities, Lua scripts
- Key files: `base.py` (models), `types/` (type system), `scripts/` (atomicity)

**rapyer/errors/:**
- Purpose: Custom exception definitions
- Contains: Error classes with contextual information
- Key files: `base.py` - all exception classes

**rapyer/fields/:**
- Purpose: Query and annotation system
- Contains: Expression DSL for Redis Search, field annotations (Index, Key, SafeLoad)
- Key files: `expression.py` (query builder), `index.py`, `key.py`, `safe_load.py` (annotations)

**rapyer/types/:**
- Purpose: Type system wrapping native Python types
- Contains: Redis-aware versions of str, int, list, dict, datetime, bytes
- Key files: `base.py` (RedisType base), `convert.py` (type conversion), individual type files

**rapyer/utils/:**
- Purpose: Shared utility functions
- Contains: Annotation manipulation, field introspection, Redis command builders
- Key files: `annotation.py`, `fields.py`, `redis.py`, `pythonic.py`

**rapyer/scripts/:**
- Purpose: Lua script execution and caching
- Contains: Script registry, template loader, variant substitution
- Key files: `registry.py` (caching), `loader.py` (templates), `lua/` (script files)

**rapyer/scripts/lua/:**
- Purpose: Lua script templates for atomic operations
- Contains: Script templates with variant placeholders
- Structure: Organized by operation category (datetime, dict, list, numeric, string)

**tests/:**
- Purpose: Test suite for Rapyer
- Contains: Unit tests, integration tests, test models
- Key files: `conftest.py` (fixtures), `models/` (shared test models)

**tests/unit/:**
- Purpose: Unit tests using FakeRedis
- Contains: Tests for individual features without Redis server
- Structure: Mirrors `rapyer/` structure (types/, pipeline/, etc.)

**tests/integration/:**
- Purpose: Integration tests using real Redis server
- Contains: End-to-end scenario tests
- Requirements: Running Redis server configured via CI

**tests/models/:**
- Purpose: Shared test model definitions
- Contains: Model classes reused across unit and integration tests
- Key files: `unit_types.py` (unit test models), other model definitions

## Key File Locations

**Entry Points:**
- `rapyer/__init__.py`: Public API exports (AtomicRedisModel, aget, afind, ainsert, alock_from_key, apipeline)
- `rapyer/init.py`: `init_rapyer()` - application startup function
- `rapyer/base.py`: AtomicRedisModel class definition

**Configuration:**
- `rapyer/config.py`: RedisConfig dataclass with defaults
- `rapyer/context.py`: Context variable for pipeline state

**Core Logic:**
- `rapyer/base.py`: CRUD operations (asave, aget, afind, adelete), locking, pipelines
- `rapyer/types/base.py`: RedisType base class, serialization/deserialization logic
- `rapyer/types/convert.py`: Type annotation to Redis type conversion
- `rapyer/fields/expression.py`: Query expression DSL and filter building

**Testing:**
- `tests/unit/conftest.py`: fake_redis_client fixture
- `tests/models/unit_types.py`: Simple test models
- `tests/conftest.py`: TTL test decorators

## Naming Conventions

**Files:**
- `{type_name}.py`: Type wrapper files (e.g., `string.py`, `integer.py`, `lst.py`, `dct.py`)
- `test_{feature}.py`: Test files (e.g., `test_initialization.py`, `test_operations.py`)
- `conftest.py`: Pytest configuration and fixtures

**Directories:**
- `lua/{category}/`: Lua scripts grouped by operation type (datetime, dict, list, numeric, string)
- `types/`: Type wrapper implementations
- `fields/`: Field annotations and expression system
- `utils/`: Utility modules
- `scripts/`: Script loading and execution
- `errors/`: Exception definitions

**Classes:**
- `Redis{Type}`: Type wrapper classes (e.g., `RedisStr`, `RedisInt`, `RedisList`)
- `{Type}Expression`: Expression classes (e.g., `EqExpression`, `GtExpression`, `AndExpression`)
- `Annotation`: Field annotation classes (e.g., `IndexAnnotation`, `KeyAnnotation`)

**Functions:**
- `a{verb}`: Async CRUD methods (e.g., `asave`, `aget`, `afind`, `ainsert`, `adelete`)
- `init_{feature}`: Initialization functions (e.g., `init_rapyer`)
- `make_{object}`: Factory functions (e.g., `make_pickle_field_serializer`)

## Where to Add New Code

**New Field Type:**
1. Create `rapyer/types/{type_name}.py` with class inheriting from `GenericRedisType` or `RedisType`
2. Implement async methods (`aset`, `aappend`, `aupdate` as needed)
3. Register in `rapyer/types/init.py:ALL_TYPES` dict
4. Add tests in `tests/unit/types/{category}/test_{type_name}.py`

**New Lua Script (for new operation):**
1. Create template in `rapyer/scripts/lua/{category}/{script_name}.lua`
2. Register in `rapyer/scripts/constants.py` with script name constant
3. Add function in `rapyer/scripts/registry.py` to handle registration
4. Call via `arun_sha()` or `run_sha()` in type wrapper methods
5. Add tests in `tests/unit/types/{category}/test_lua_scripts.py`

**New Annotation Type:**
1. Create `rapyer/fields/{annotation_name}.py` with class inheriting from desired base
2. Use in type hints: `field: Type[SomeAnnotation]`
3. Check for annotation in `__init_subclass__` using `has_annotation()`
4. Document in docstrings and changelog

**New Model Operation:**
1. Add method to `AtomicRedisModel` in `rapyer/base.py`
2. For operations needing atomicity: use pipeline via context variable
3. For complex operations: create Lua script in `rapyer/scripts/lua/`
4. Add tests in `tests/unit/test_{feature}.py` or `tests/integration/test_{feature}.py`

**Utilities:**
- General annotation helpers: `rapyer/utils/annotation.py`
- Field metadata utilities: `rapyer/utils/fields.py`
- Redis command builders: `rapyer/utils/redis.py`
- Python introspection helpers: `rapyer/utils/pythonic.py`

## Special Directories

**rapyer/scripts/lua/:**
- Purpose: Lua script source templates
- Generated: No, committed to repo
- Committed: Yes
- Format: Template with `--[[PLACEHOLDER]]` markers for variant substitution
- Variants: `REDIS_VARIANT` (Redis 6.0+), `FAKEREDIS_VARIANT` (FakeRedis compatibility)

**rapyer/types/__pycache__/:**
- Purpose: Python bytecode cache
- Generated: Yes, automatically by Python
- Committed: No

**tests/models/:**
- Purpose: Shared model definitions for testing
- Generated: No, hand-written
- Committed: Yes
- Reusability: Used by both unit and integration tests

**rapyer/scripts/lua/:**
- Lua Template Language: Lua 5.1 (Redis server standard)
- Helper Functions: `cjson.encode()`, `cjson.decode()` for serialization
- Key Commands: `redis.call()`, `redis.pcall()` for Redis operations

---

*Structure analysis: 2026-02-05*
