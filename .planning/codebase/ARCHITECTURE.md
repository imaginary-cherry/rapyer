# Architecture

**Analysis Date:** 2026-02-05

## Pattern Overview

**Overall:** ORM (Object-Relational Mapping) with Async Redis Backend

**Key Characteristics:**
- Pydantic v2-based models with Redis JSON as persistence layer
- Atomic operations using Lua scripts for race-condition safety
- Context variable injection for pipeline/transaction management
- Type conversion system that wraps Python types with Redis-aware wrappers
- Support for nested models with full Redis functionality preserved

## Layers

**Model Layer (Application):**
- Purpose: User-defined Pydantic models extending `AtomicRedisModel`
- Location: User code or `tests/models/`
- Contains: Business logic models with field definitions, custom methods
- Depends on: `rapyer.base.AtomicRedisModel`, field annotations
- Used by: Orchestration and business logic in applications

**ORM Core (`rapyer.base`):**
- Purpose: Base model class and high-level CRUD operations
- Location: `rapyer/base.py`
- Contains: `AtomicRedisModel` class with async methods (`asave`, `aget`, `afind`, `adelete`, `alock`, `apipeline`)
- Depends on: Pydantic, Redis client, type converters, field expressions
- Used by: All user models and internal operations

**Type System (`rapyer/types/`):**
- Purpose: Redis-aware type wrappers that execute operations atomically
- Location: `rapyer/types/*.py` (string, integer, float, byte, datetime, lst, dct)
- Contains: `RedisStr`, `RedisInt`, `RedisList`, `RedisDict`, etc. inheriting from `RedisType`
- Depends on: Pydantic TypeAdapter, context variables, Lua script runner
- Used by: Models automatically wrap fields into these types via `RedisConverter`

**Script/Lua Layer (`rapyer/scripts/`):**
- Purpose: Atomic Lua script execution for operations that need atomicity
- Location: `rapyer/scripts/` (registry, loader) and `rapyer/scripts/lua/` (Lua implementations)
- Contains: Lua scripts for list operations, dict operations, numeric increments, datetime manipulations
- Depends on: Redis EVALSHA, script registration and caching
- Used by: Type wrappers execute scripts to maintain atomicity

**Field Expression System (`rapyer/fields/`):**
- Purpose: Query expression building for Redis Search indexing
- Location: `rapyer/fields/expression.py`, `rapyer/fields/index.py`, `rapyer/fields/key.py`
- Contains: Expression classes (`ExpressionField`, `AtomicField`, comparison operators)
- Depends on: Pydantic field info, annotation introspection
- Used by: `afind()` method builds filter queries from expressions

**Type Conversion (`rapyer/types/convert.py`):**
- Purpose: Transform Python type annotations into Redis type wrappers
- Location: `rapyer/types/convert.py`
- Contains: `RedisConverter` class that processes annotations and creates new types
- Depends on: Type introspection, dynamic type creation
- Used by: `__init_subclass__` in `AtomicRedisModel` to wrap all fields

**Context Management (`rapyer/context.py`):**
- Purpose: Store and retrieve active Redis pipeline in context variable
- Location: `rapyer/context.py`
- Contains: `_context_var` - ContextVar holding current pipeline or Redis client
- Depends on: Python contextvars
- Used by: All type operations check context for active pipeline

**Utilities (`rapyer/utils/`):**
- Purpose: Supporting utilities for annotations, fields, redis operations
- Location: `rapyer/utils/*.py`
- Contains: Annotation helpers, field metadata extraction, redis command builders
- Depends on: Pydantic internals, type introspection
- Used by: Type conversion, field wrapping, pipeline operations

**Initialization (`rapyer/init.py`):**
- Purpose: Setup and teardown of Rapyer ecosystem
- Location: `rapyer/init.py`
- Contains: `init_rapyer()`, `teardown_rapyer()` functions
- Depends on: Script registration, model initialization
- Used by: Application startup to configure all models globally

## Data Flow

**Model Creation Flow:**

1. User defines class extending `AtomicRedisModel`
2. `__init_subclass__` triggered, calls `RedisConverter` on each field annotation
3. Converter wraps native types with Redis types (e.g., `str` → `RedisStr`)
4. `make_pickle_field_serializer` added for non-native types (for pickling support)
5. Model registered in `REDIS_MODELS` global list
6. Fields now support atomic operations automatically

**Write Flow (asave/aupdate):**

1. User modifies model: `model.field = value` or `await model.field.aappend(item)`
2. `__setattr__` called, sets value on model and checks for active context pipeline
3. If pipeline active: Serializes field, adds SET command to pipeline
4. If no pipeline: Executes directly on Redis client
5. On pipeline exit: Context manager executes all commands atomically
6. TTL refreshed if configured

**Read Flow (aget/afind):**

1. User calls `await Model.aget(key)` or `await Model.afind(...)`
2. Retrieves JSON from Redis using `json().get()` or `json().mget()`
3. `model_validate()` converts raw data back to model (triggers validators)
4. Validators deserialize pickled complex types if needed
5. Model fields are re-wrapped with Redis types, linking to parent
6. TTL refreshed if configured

**Operation Flow (List/Dict operations):**

1. User calls `await model.list_field.aappend(item)` or `dict_field.aupdate(k=v)`
2. Checks if pipeline active via context variable
3. If pipeline: Adds serialized command to pipeline (deferred)
4. Either way: Updates local Python object immediately
5. Returns or awaits Redis response if not in pipeline
6. Complex types trigger Lua script execution for atomic operations

**Search Flow (afind with expressions):**

1. User builds expression: `Model.field == value & Model.other > 10`
2. Expression objects chain comparisons via `__and__`, `__or__`, `__invert__`
3. `afind()` converts expression to Redis Search filter syntax
4. Query executed against indexed model
5. Results deserialized same as read flow

## State Management

**Client State:**
- Global `AtomicRedisModel.Meta.redis` holds Redis client
- Configured per-class via `init_rapyer(redis=...)`
- Can be overridden at runtime via `Model.Meta.redis = new_client`

**Pipeline State:**
- Stored in context variable `_context_var`
- Set when entering `async with apipeline()` context
- All nested operations check this context
- On exit: executed atomically with `transaction=True`

**Local State:**
- Models hold Python objects in memory
- Nested models/collections link to parent via `_base_model_link`
- Field names and paths computed from links
- Json paths constructed for Redis JSON operations

**Serialization State:**
- `REDIS_DUMP_FLAG_NAME` context flag signals serialization mode
- Pickle serialization applied for complex types unless `prefer_normal_json_dump=True`
- `SafeLoadAnnotation` allows deserialization failures to be soft (return None)
- Failed field tracking in `_failed_fields` on model instance

## Key Abstractions

**RedisType:**
- Purpose: Base class for all Redis-wrapped types
- Examples: `rapyer/types/string.py`, `rapyer/types/integer.py`, `rapyer/types/lst.py`, `rapyer/types/dct.py`
- Pattern: Inherits from both original type (`str`, `int`, `list`, `dict`) and `GenericRedisType`
- Provides: Async methods (`aset`, `aappend`, `aupdate`), serialization/deserialization, TTL refresh

**AtomicRedisModel:**
- Purpose: Base Pydantic model with Redis persistence
- Location: `rapyer/base.py`
- Pattern: Metaclass-style setup via `__init_subclass__` transforms all fields
- Provides: CRUD methods, locking, pipeline support, indexing, expression filtering

**Expression:**
- Purpose: DSL for building Redis Search queries
- Examples: `rapyer/fields/expression.py` (EqExpression, GtExpression, AndExpression, etc.)
- Pattern: Composite with operator overloading (`==`, `>`, `&`, `|`, `~`)
- Provides: `create_filter()` method converts to Redis RESPatch syntax

**RedisConverter:**
- Purpose: Transforms type annotations during class definition
- Location: `rapyer/types/convert.py`
- Pattern: Visitor-like conversion of generic and flat types
- Provides: `convert_flat_type()`, `covert_generic_type()` to wrap types

## Entry Points

**Application Entry Point:**
- Location: User application code
- Triggers: Application startup
- Responsibilities: Define models, call `init_rapyer()`, create/query models

**Initialization Entry Point:**
- Location: `rapyer/init.py:init_rapyer()`
- Triggers: Application startup after importing models
- Responsibilities: Configure Redis client, register Lua scripts, create search indexes, initialize model expression fields

**Model Class Entry Point:**
- Location: When a class extends `AtomicRedisModel`
- Triggers: Class definition (via `__init_subclass__`)
- Responsibilities: Register model globally, wrap fields with Redis types, set up serializers/validators

**Async Operation Entry Points:**
- `await model.asave()` - Persist model
- `await Model.aget(key)` - Retrieve single model
- `await Model.afind(...)` - Query multiple models
- `async with model.alock(...)` - Atomic multi-step transaction
- `async with model.apipeline()` - Batch operations atomically

## Error Handling

**Strategy:** Try-except with custom error classes, fallback to warning logs

**Patterns:**
- `KeyNotFound` - Raised when model key doesn't exist in Redis
- `CantSerializeRedisValueError` - Raised when pickle deserialization fails (unless SafeLoad)
- `UnsupportedIndexedFieldError` - Raised when complex type marked as indexed
- `ValidationError` (Pydantic) - Raised on model validation failure
- `NoScriptError` - Caught and handled by re-registering Lua scripts
- `ResponseError` - Logged as warning or raised based on `ignore_redis_error` flag
- Lua script execution errors caught and retried with script re-registration

## Cross-Cutting Concerns

**Logging:**
- Module logger at `rapyer` level
- Warnings for SafeLoad failures, swallowed Redis errors
- Debug logs for skipped keys during validation

**Validation:**
- Pydantic validators on deserialization
- Field validators for pickle decode/encode
- Model validators for sub-model assignment
- TTL enforcement via separate `test_ttl_enforcement.py`

**Authentication:**
- None built-in; handled by Redis client configuration
- Credentials passed to `redis.asyncio.from_url()` or Redis client constructor

**Serialization:**
- JSON mode for Redis JSON compatibility
- Base64-encoded pickle for complex types
- Context flag `REDIS_DUMP_FLAG_NAME` to toggle serialization behavior

---

*Architecture analysis: 2026-02-05*
