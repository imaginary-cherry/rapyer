<!-- refreshed: 2026-07-06 -->
# Architecture

**Analysis Date:** 2026-07-06

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                     User-defined Pydantic Models                     │
│           (subclass `AtomicRedisModel`, declare fields)              │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          AtomicRedisModel                            │
│                          `rapyer/base.py`                            │
│  - CRUD (aget/afind/ainsert/aupdate/adelete/aget_or_create)          │
│  - key/pk/json_path computation, TTL, indexing, dump/exclude logic   │
└───────┬───────────────────┬───────────────────┬─────────────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌──────────────────┐   ┌────────────────────────┐
│ Field Types    │   │ Actions (TTL     │   │ Context (contextvars)  │
│ `rapyer/types/`│   │  refresh system) │   │ `rapyer/context.py`    │
│ - inline redis │   │ `rapyer/actions  │   │ - active pipeline      │
│   scalar types │   │      .py`        │   │ - active JSON client   │
│ - special (SF) │   └──────────────────┘   └────────────────────────┘
│   types (own   │
│   Redis key)   │
│ - relational   │
│   (FK) types   │
└───────┬────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Scripts Layer (Lua / atomicity)                    │
│         `rapyer/scripts/registry.py`, `rapyer/scripts/loader.py`,    │
│                     `rapyer/scripts/lua/**/*.lua`                    │
│  - EVALSHA-cached scripts for numeric/string/list/dict mutations,    │
│    datetime add, and the atomic `get_or_create` script that stitches │
│    in per-special-field Lua save/load snippets at registration time  │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    redis-py asyncio client / RedisJSON /             │
│                    RediSearch (`Meta.redis`, `Meta.redis_json`)      │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `AtomicRedisModel` | Base ORM model: pydantic `BaseModel` subclass that owns key derivation, JSON path computation, CRUD, indexing, TTL refresh wiring, `__init_subclass__` metaclass-like field rewriting | `rapyer/base.py` |
| `RedisConfig` (`Meta`) | Per-model configuration: redis client, TTL, refresh policy, type-conversion table, safe-load flags | `rapyer/config.py` |
| Context vars | Tracks the "current" pipeline/JSON-client so nested field/model operations transparently batch into an outer transaction | `rapyer/context.py` |
| Actions / TTL refresh | `mark_actions` decorator + `ActionGroup` flags classify every mutating/reading method; installs TTL-refresh wrapper per model at class-build time | `rapyer/actions.py` |
| Field types (inline) | Redis-serializable wrappers for `int/float/str/bytes/dict/list/datetime` that mirror in-place mutation into pipelines | `rapyer/types/integer.py`, `rapyer/types/float.py`, `rapyer/types/string.py`, `rapyer/types/byte.py`, `rapyer/types/dct.py`, `rapyer/types/lst.py`, `rapyer/types/datetime.py`, `rapyer/types/generic.py` |
| Special fields (SF) | Field types stored under their *own* Redis key (not inline JSON): `RedisSet` (Redis SET), `RedisPriorityQueue` (Redis sorted set) | `rapyer/types/redis_set.py`, `rapyer/types/priority_queue.py`, `rapyer/types/special.py` |
| Relational fields (FK) | `ForeignKey[T]` — lazy reference to another model, stored inline as a key string, hydrated via `afetch()` | `rapyer/types/foreign_key.py`, `rapyer/types/relational.py` |
| Type conversion engine | Rewrites a model's plain-Python annotations into per-field dynamic `BaseRedisType` subclasses at subclass-creation time | `rapyer/types/convert.py`, `rapyer/utils/annotation.py` |
| Fields/annotations DSL | `Key[...]`, `Index[...]`, safe-load marker, filter `Expression` tree for `afind` | `rapyer/fields/key.py`, `rapyer/fields/index.py`, `rapyer/fields/safe_load.py`, `rapyer/fields/expression.py` |
| Scripts registry/loader | Loads `.lua` templates from package resources, patches Redis/fakeredis variant differences, `SCRIPT LOAD`s and caches SHAs, injects special-field dispatch tables, retries on `NOSCRIPT` | `rapyer/scripts/registry.py`, `rapyer/scripts/loader.py`, `rapyer/scripts/constants.py` |
| Lua scripts | Per-operation atomic scripts (numeric ops, string ops, list ops, dict pop, datetime add, atomic get-or-create) | `rapyer/scripts/lua/**/*.lua` |
| Errors | Exception hierarchy rooted at `RapyerError` | `rapyer/errors/base.py`, `rapyer/errors/find.py`, `rapyer/errors/delete.py`, `rapyer/errors/__init__.py` |
| Result types | Typed return values for delete/get-or-create operations | `rapyer/result.py` |
| Module init/teardown | Registers Lua scripts, wires each registered model's `Meta.redis`, creates RediSearch indexes, resolves FK forward references | `rapyer/init.py` |
| Public API | Package entry point re-exporting the model class and module-level free functions | `rapyer/__init__.py` |

## Pattern Overview

**Overall:** Active-Record ORM over Redis, built as a Pydantic v2 extension. Each `AtomicRedisModel` subclass *is* both the schema definition and the data-access object (Active Record), not a separate mapper/repository. There is no separate persistence-layer abstraction — `AtomicRedisModel` methods talk to Redis directly (via `redis-py` asyncio + RedisJSON + RediSearch), mediated by a metaclass-style field-rewriting step that happens once per model class.

**Key Characteristics:**
- **Metaclass-via-`__init_subclass__`:** Every `AtomicRedisModel` subclass is intercepted in `__init_subclass__` (`rapyer/base.py:322`) which walks its annotations and replaces plain Python types with dynamically generated `BaseRedisType` subclasses (one per field, carrying `field_name`/`original_type`/`safe_load`), wires pickle-based (de)serializers, detects special/relational fields, and registers the class in the global `REDIS_MODELS` registry.
- **Contextvar-based implicit pipelining:** Rather than passing a `pipeline` object explicitly, `rapyer/context.py` stores the "active" pipeline/JSON-client in `contextvars.ContextVar`. Any field mutation (`__setattr__`, `RedisSet.add`, `RedisList` ops, etc.) checks `self.pipeline`/`self.client` and transparently queues a command if a pipeline context is open, or issues an immediate. This makes `async with model.apipeline():` batch arbitrarily nested mutations without threading a client through every call.
- **Action-group TTL system:** All mutating/reading async methods are tagged with `ActionGroup` flags via `@mark_actions(...)`. At class-build time (`install_marked_action_methods`, `rapyer/actions.py:359`) each tagged method is either wrapped (to auto-refresh TTL after the outermost call completes) or left unwrapped, decided once against `Meta.refresh_ttl`/`Meta.ttl` — avoiding a per-call runtime check.
- **Two orthogonal storage strategies per field:** (1) *inline* fields serialize into the model's single RedisJSON document; (2) *special fields* (SF: `RedisSet`, `RedisPriorityQueue`) live under a derived, separate Redis key so their native structures (SET, ZSET) can be mutated with native Redis commands instead of round-tripping the whole JSON doc.
- **Redis Lua scripts for atomicity:** True atomic operations (numeric add/mul/div, string concat, dict pop, list slice-remove, and the flagship `get_or_create`) are implemented as Lua scripts loaded once via `SCRIPT LOAD` and invoked with `EVALSHA`, with automatic re-registration on `NOSCRIPT`.
- **Foreign keys are inline, lazy, unresolved-by-default references** — no ORM-style joins or automatic cascading; the parent stores only the target's Redis key string.

## Layers

**Model/Schema layer:**
- Purpose: Define models (`class Foo(AtomicRedisModel): ...`), let `__init_subclass__` rewrite fields into Redis-aware types, and expose CRUD + TTL + indexing entry points.
- Location: `rapyer/base.py`
- Contains: `AtomicRedisModel`, module-level free functions (`aget`, `afind`, `ainsert`, `adelete_many`, `aget_or_create`, `apipeline`, `alock_from_key`), `REDIS_MODELS` registry.
- Depends on: config, context, actions, errors, fields, types, scripts, result, utils.
- Used by: application code that subclasses `AtomicRedisModel`; `rapyer/init.py` at startup.

**Field-type layer:**
- Purpose: Represent every supported Python/Redis type as a `BaseRedisType` subclass that knows how to serialize itself and (for mutable containers) mirror in-place mutations into the active pipeline.
- Location: `rapyer/types/`
- Contains: `base.py` (`BaseRedisType`, `RedisType` — inline types base), `special.py` (`SpecialFieldType` — SF base), `relational.py` (`RelationalFieldType` — FK base), concrete types (`integer.py`, `float.py`, `string.py`, `byte.py`, `dct.py`, `lst.py`, `datetime.py`, `generic.py`, `redis_set.py`, `priority_queue.py`, `foreign_key.py`), `convert.py` (dynamic subclass factory), `init.py` (`ALL_TYPES` mapping).
- Depends on: `rapyer/actions.py`, `rapyer/context.py`, `rapyer/scripts/loader.py` (SF Lua snippets), `rapyer/errors`.
- Used by: `AtomicRedisModel.__init_subclass__` (field rewriting), `rapyer/config.py` (`redis_type` mapping default).

**Actions/TTL layer:**
- Purpose: Cross-cutting classification of "what kind of operation is this" (`ActionGroup`) and automatic TTL refresh at the outermost call boundary.
- Location: `rapyer/actions.py`
- Contains: `ActionGroup` flag enum, `mark_actions` decorator, `TargetSource` enum, `install_marked_action_methods`/`install_action_for_meta` (install-time wrapping), context-var-based action-target collection (`_action_context`).
- Depends on: `rapyer/context.py` (nested pipeline reuse via `ensure_pipeline`).
- Used by: nearly every async method on `AtomicRedisModel`, `RedisType`, `SpecialFieldType`, `ForeignKey`.

**Context layer:**
- Purpose: Hold the ambient pipeline/JSON-client so deeply nested code (field types, sub-models) can detect "am I inside a pipeline" without explicit parameter threading.
- Location: `rapyer/context.py`
- Contains: `_context_pipe`, `_context_pipe_json` (`contextvars.ContextVar`), `ensure_pipeline` (reuse-or-create pipeline context manager), `pipeline_with_execution`, `with_pipe_context`, `get_pipe_json`.
- Depends on: `redis.asyncio.client.Pipeline`.
- Used by: `base.py`, all field types, `actions.py`.

**Config layer:**
- Purpose: Per-model-class settings object (`Meta`), including the Redis client, TTL, refresh policy, and the type-conversion table.
- Location: `rapyer/config.py`
- Contains: `RedisConfig` (pydantic `BaseModel`), `DEFAULT_CONNECTION`.
- Depends on: `rapyer/actions.py` (`ActionGroup` for `refresh_ttl` type), `rapyer/errors`.
- Used by: every `AtomicRedisModel.Meta`, `rapyer/init.py`.

**Scripts layer:**
- Purpose: Load, patch (Redis vs fakeredis differences), register, and invoke Lua scripts for atomic numeric/string/list/dict ops and the atomic `get_or_create` script; handle `NOSCRIPT` re-registration transparently.
- Location: `rapyer/scripts/`
- Contains: `registry.py` (`SCRIPT_REGISTRY`, `register_scripts`, `arun_sha`/`run_sha`, `handle_noscript_error`), `loader.py` (template loading + variant placeholder substitution, SF snippet loading via `importlib.resources`), `constants.py` (script name constants), `lua/**/*.lua` (script bodies).
- Depends on: `rapyer/errors`.
- Used by: field types with atomic in-place ops (`RedisInt.__iadd__` style methods, `RedisDict.apop`, etc.), `AtomicRedisModel.aget_or_create`, `rapyer/init.py` (registration at startup).

**Fields/DSL layer:**
- Purpose: Annotation markers (`Key[...]`, `Index[...]`, safe-load) and the filter-expression tree used by `afind(...)`.
- Location: `rapyer/fields/`
- Contains: `key.py` (`Key`, `KeyAnnotation`, `RapyerKey`), `index.py` (`Index`, `IndexAnnotation`), `safe_load.py` (`SafeLoad`, `SafeLoadAnnotation`), `expression.py` (`Expression` tree: `AtomicField`, `ExpressionField`, `Eq/Ne/Gt/Lt/Gte/LteExpression`, `And/Or/NotExpression`).
- Depends on: `rapyer/types/datetime.py` (Index datetime coercion), `rapyer/errors`, `rapyer/types/base.py`.
- Used by: `AtomicRedisModel.redis_schema`/`create_expressions`/`afind`.

**Errors layer:**
- Purpose: Single exception hierarchy for all rapyer-raised errors.
- Location: `rapyer/errors/`
- Contains: `base.py` (`RapyerError` and most concrete errors), `find.py` (query/index/serialization errors), `delete.py` (`BadDeleteActionError`), `__init__.py` (re-exports + deprecated-alias shim).
- Depends on: nothing internal.
- Used by: every layer.

**Utils layer:**
- Purpose: Small shared helpers with no domain state.
- Location: `rapyer/utils/`
- Contains: `annotation.py` (`TypeConverter` protocol, `replace_to_redis_types_in_annotation`, `has_annotation`, `strip_optional`, `field_with_flag`), `fields.py` (pydantic annotation collection, JSON-serializability probing), `pythonic.py` (`safe_issubclass`, `inject_at_paths`), `redis.py` (pipeline-based load/delete/scan helpers used by `base.py`).
- Depends on: `rapyer/context.py`, `rapyer/errors`.
- Used by: `base.py`, `types/`, `config.py`.

## Data Flow

### Primary Read Path (`aget`)

1. Caller invokes `MyModel.aget(key)` (`rapyer/base.py:582`), decorated with `@mark_actions(ActionGroup.READ, ActionGroup.FETCH, target=TargetSource.RESULT)`.
2. `_resolve_key` normalizes the key to `"ClassName:pk"` form.
3. If the model has no special fields, a single `JSON.GET key $` call is issued (`rapyer/base.py:587`). If it does contain SF fields, `execute_load_pipeline` (`rapyer/utils/redis.py:31`) builds one transactional pipeline containing `JSON.MGET` plus one Redis command per special field (queued via `queue_special_loads_in_pipeline`, `rapyer/base.py:656`), executes it once, and returns `(models_dump, plans_per_key, sf_raw)`.
4. `inject_at_paths` (`rapyer/utils/pythonic.py`) merges the raw SF results back into the JSON dump at the recorded paths.
5. `create_redis_model` (`rapyer/base.py:672`) calls `cls.model_validate(...)` (pydantic validation triggers per-field custom validators/pickle decoding) and sets `model.key`.
6. Because the method is `target=TargetSource.RESULT`, the returned model is auto-registered for TTL refresh (`register_from_result`), and — if this was the outermost `mark_actions` call on the stack — `flush_action_targets` refreshes TTL on all `_ttl_keys()` (main key + every SF key) in one pipeline.

### Write Path (`asave` / `ainsert`)

1. `asave` (`rapyer/base.py:470`) is tagged `@mark_actions(ActionGroup.UPDATE, ActionGroup.CREATE)`.
2. `self.redis_dump()` produces a `mode="json"` pydantic dump with `context={REDIS_DUMP_FLAG_NAME: True}` (this flag switches on redis-specific serializers: pickling of non-JSON-safe fields, FK key-string serialization, SF exclusion via `build_redis_dump_exclude`).
3. Inside `ensure_pipeline(self.Meta)` (reuses an outer pipeline if present, else opens+executes a new transactional one), `pipe_json.set(self.key, self.json_path, model_dump)` queues the RedisJSON write.
4. Each special field is saved separately via `field.asave_special()` (e.g. `RedisSet`/`RedisPriorityQueue` write to their own key) — these calls happen *inside* the same `ensure_pipeline` block so they land in the same transaction as the main JSON write.
5. On pipeline context exit, `pipe.execute()` runs; on `NoScriptError` (only relevant for EVALSHA-based ops elsewhere), scripts are re-registered and retried (`rapyer/base.py:1284` `_apipeline`).

### Atomic `get_or_create` Path

1. `AtomicRedisModel.aget_or_create` (`rapyer/base.py:796`) walks every special field (`_iter_special_fields`) to build `sf_args` triples: `(lua_type_name, special_key, save_payload)`.
2. A single `EVALSHA` call to the registered `atomic_get_or_create` script (`rapyer/scripts/lua/atomic/get_or_create.lua`) does, server-side and atomically: `EXISTS` check on the main key → if it exists, `JSON.GET` the current doc and run each field's `SF_LOAD[type]` snippet, returning `{0, current_doc, ...sf_loads}`; if it does not exist, run every field's `SF_SAVE[type]` snippet (writing SF Redis structures) *before* `JSON.SET`ting the main document last (so the "existence sentinel" — the main key — is only committed once all SF saves succeeded), returning `{1, main_data}`.
3. `SF_SAVE`/`SF_LOAD` dispatch tables are spliced into the script template at *registration* time (`_inject_sf_dispatch`, `rapyer/scripts/registry.py:64`) by iterating `SpecialFieldType.__subclasses__()` and inlining each subclass's `lua_save_snippet()`/`lua_load_snippet()` Lua function literals — so per-call `ARGV` only ships identifiers/payloads, not script bodies.
4. Python side interprets `flag` (`1`=created, `0`=found), reconstructs the model via `create_redis_model`, and returns `GetOrCreateResult(value=..., status=CREATED|FOUND)`.

**State Management:**
- No client-side cache/identity map: every `aget`/`afind`/`aload` round-trips to Redis and re-validates via pydantic.
- The only "in-memory state that must stay consistent with Redis" is (a) `_base_model_link` (parent pointer used to compute `field_path`/`json_path`/`key` for nested/field objects) and (b) local mirrors of `RedisSet`/`RedisList`/`RedisDict` contents, which are mutated optimistically alongside the pipeline command being queued (see `RedisSet.add`, `rapyer/types/redis_set.py:48`).
- Locking: `alock`/`alock_from_key` (`rapyer/base.py:972`) uses a Redis-native lock (`redis.lock`, `rapyer/utils/redis.py:16`, keyed `f"{key}/{action}:lock"`) to serialize read-modify-write sequences across processes.

## Key Abstractions

**`AtomicRedisModel` (`rapyer/base.py`):**
- Purpose: Base class every user model inherits from; combines schema (pydantic fields) + persistence (CRUD methods) + Redis key/path computation.
- Examples: any user-defined model; internally, `redis_dump`, `key`, `pk`, `field_path`, `json_path` properties.
- Pattern: Active Record. `Self`-returning fluent methods (`asave`, `aupdate`) mutate the instance and issue Redis writes together.

**`BaseRedisType` / `RedisType` / `SpecialFieldType` / `RelationalFieldType` (`rapyer/types/base.py`, `rapyer/types/special.py`, `rapyer/types/relational.py`):**
- Purpose: Three-way split of "how does this field type persist itself": inline JSON value (`RedisType`), separate Redis key with native structure (`SpecialFieldType`), and inline key-reference to another model (`RelationalFieldType`).
- Examples: `RedisInt`/`RedisStr`/`RedisList`/`RedisDict`/`RedisDatetime` (inline); `RedisSet`/`RedisPriorityQueue` (special); `ForeignKey` (relational).
- Pattern: Strategy — `AtomicRedisModel` treats all three uniformly through shared properties (`key`, `field_path`, `json_path`, `client`) but each implements `asave`/`aload`/dump-exclusion differently.

**Dynamic per-field subclassing (`RedisConverter`, `rapyer/types/convert.py`):**
- Purpose: Every field gets its *own* runtime-generated subclass of the relevant `BaseRedisType` (e.g. a field `count: int` becomes a unique `RedisInt` subclass) so `field_name`/`original_type`/a cached `TypeAdapter` can be baked in as class attributes without instances needing to carry that state.
- Examples: `_build_redis_subclass`, `convert_flat_type`, `covert_generic_type`.
- Pattern: Type-level memoization / code generation via `types.new_class`.

**Action-group / TTL refresh system (`ActionGroup`, `mark_actions`, `rapyer/actions.py`):**
- Purpose: Declaratively classify every persistence method by the kind of Redis operation it performs, then automatically refresh TTL on the affected key(s) exactly once per outermost call, based on `Meta.refresh_ttl` policy.
- Examples: `@mark_actions(ActionGroup.READ, ActionGroup.FETCH, target=TargetSource.RESULT)` on `aget`.
- Pattern: Decorator + install-time (per-model) wrapping decision, contextvar-based target accumulation, similar to an AOP "around advice".

**Expression tree (`rapyer/fields/expression.py`):**
- Purpose: Build RediSearch query strings from Python comparison operators (`Model.field == value`) for `afind(...)`.
- Examples: `EqExpression`, `AndExpression`, `OrExpression`, `NotExpression`.
- Pattern: Composite/interpreter — each node implements `create_filter()` returning a RediSearch query fragment; `&`/`|`/`~` compose nodes.

**Special-field Lua dispatch (`SpecialFieldType.lua_save_snippet`/`lua_load_snippet`, `rapyer/scripts/registry.py:_inject_sf_dispatch`):**
- Purpose: Let each SF type contribute its own atomic save/load Lua logic without the core `get_or_create.lua` script knowing about concrete SF types.
- Examples: `rapyer/scripts/lua/sf/redis_set/{save,load}.lua`, `rapyer/scripts/lua/sf/redis_priority_queue/{save,load}.lua`.
- Pattern: Plugin registry keyed by `lua_type_name()`, resolved via `__subclasses__()` at script-registration time.

## Entry Points

**`rapyer/__init__.py`:**
- Location: `rapyer/__init__.py`
- Triggers: `import rapyer`.
- Responsibilities: Re-exports `AtomicRedisModel`, `init_rapyer`/`teardown_rapyer`, module-level free functions (`aexists`, `aget`, `aget_or_create`, `afind`, `afind_one`, `find_redis_models`, `ainsert`, `adelete_many`, `alock_from_key`, `apipeline`), and result types (`DeleteResult`, `GetOrCreateResult`, `GetOrCreateStatus`, `RapyerDeleteResult`). Calls `resolve_forward_refs()` immediately at import time so pydantic generic result models can reference `AtomicRedisModel`.

**`init_rapyer()` (`rapyer/init.py:17`):**
- Location: `rapyer/init.py`
- Triggers: Called once by the application at startup (usually with a Redis URL or client).
- Responsibilities: Resolves forward refs / FK targets (`resolve_relational_targets`), connects/wraps the Redis client, detects fakeredis, registers all Lua scripts (`register_scripts`), assigns `Meta.redis`/`Meta.ttl`/`Meta.prefer_normal_json_dump` onto every registered model, calls `model.init_class()` (builds `Expression` fields for `afind`), and creates/recreates RediSearch indexes for models with `Index[...]` fields.

**`teardown_rapyer()` (`rapyer/init.py:69`):**
- Location: `rapyer/init.py`
- Triggers: Application shutdown.
- Responsibilities: Closes every distinct Redis client referenced by registered models' `Meta.redis`.

**Model class definition (`AtomicRedisModel.__init_subclass__`, `rapyer/base.py:322`):**
- Location: `rapyer/base.py`
- Triggers: Python executes this automatically the moment `class Foo(AtomicRedisModel): ...` is defined (i.e. at import time of the user's model module — before `init_rapyer()` runs).
- Responsibilities: Detects `Key`/`SafeLoad` annotated fields, converts all field annotations into their per-field Redis type subclasses, installs pickle serializers/validators for non-JSON-safe fields, classifies fields into `_special_field_names`/`_relational_field_names`/`_contain_sf`/`_contain_fk`, installs action-wrapped methods (`build_redis_model`), and registers the class into the global `REDIS_MODELS` list (raising `DuplicateModelNameError` on a name collision).

## Model-to-Redis-Key Mapping

- **Main document key:** `f"{cls.class_key_initials()}:{pk}"` where `class_key_initials()` defaults to `cls.__name__` (`rapyer/base.py:298`, `:306`). `pk` is either a random `uuid4` string (default `_pk` `PrivateAttr`) or, if a field is annotated `Key[...]`, the value of that field (`AtomicRedisModel.pk` property, `rapyer/base.py:174`).
- **Storage format:** The whole model is one RedisJSON document at that key, written/read via `redis.json()` (`JSON.SET`/`JSON.GET`/`JSON.MGET` with a `$`-rooted JSONPath). Nested `AtomicRedisModel` fields live at sub-paths within the same document (`field_path`/`json_path` properties walk `_base_model_link` to build the dotted path, e.g. `$.inner.tasks`).
- **Special-field keys:** Each SF field gets its own key: `f"__rapyer_special__:{model_key}:{dotted_field_path}"` (`SpecialFieldType.special_field_key`, `rapyer/types/special.py:24`) — e.g. `__rapyer_special__:MyModel:abc123:tasks`. These are tracked as "detached" keys alongside the main key by `_all_keys_for_key` (`rapyer/base.py:560`) so delete/TTL-refresh operations sweep them too.
- **Foreign-key values:** Stored *inline* in the parent JSON document as the plain key string of the target (e.g. `"Author:abc-123"`) — no separate storage; resolution is lazy via `ForeignKey.afetch()` which calls the target class's `aget`.
- **RediSearch index name:** `f"idx:{cls.class_key_initials()}"` (`AtomicRedisModel.index_name`, `rapyer/base.py:277`), created over the `f"{cls.class_key_initials()}:"` key prefix, `IndexType.JSON`, only for fields annotated `Index[...]` (including nested model fields, recursively via `redis_schema`).
- **Class resolution from key:** Free functions (`aget`, `afind`, `adelete_many` at module scope) resolve `"ClassName:pk"` back to a registered model class by splitting on `:` and looking up `__name__` in `REDIS_MODELS` (`_resolve_model_class`, `rapyer/base.py:1100`) — this is why model class names must be globally unique (enforced in `__init_subclass__`).

## Foreign Keys and Cascade Behavior

- `ForeignKey[T]` (`rapyer/types/foreign_key.py`) is a `RelationalFieldType` that wraps either a target model instance or a plain key string. On the wire it always serializes to just the target's key string (`_serialize` in `__get_pydantic_core_schema__`), so the parent document never embeds the child's data.
- Resolution is explicit and lazy: attribute access on an unresolved FK raises `NotResolvedError`; the caller must `await fk.afetch()` first, which fetches the target via `target_cls.aget(self._target_key)` and caches it in `self._value`. `aunload()` drops the cached value while preserving the key.
- Target-class resolution happens once, globally, in `resolve_relational_targets()` (`rapyer/types/relational.py:93`), called from `init_rapyer()` after all models are registered — this is what lets forward references (`ForeignKey["Author"]`) and self-references work, and caches the resolved class on the field type so `afetch()` never re-does registry lookups.
- **No automatic cascade delete or cascade save exists.** Deleting a model that holds a `ForeignKey` to another model does not delete the referenced model, and deleting a referenced model does not clean up parents that reference it — cascade behavior, if needed, is the application's responsibility. `_contain_fk`/`_relational_field_names` (set in `__init_subclass__`) exist only to let `redis_dump`, `create_expressions`, and the SF/FK detection machinery know a field/model *contains* a relational reference — they are not used for cascading deletes.
- `contains_fk_field()` on `BaseRedisType`/`AtomicRedisModel` lets container types (e.g. `list[ForeignKey[Author]]`) and nested models propagate "I contain an FK" up the type tree, purely for bookkeeping (currently used by `__init_subclass__`'s field classification, not by any delete/cascade code path).

## Architectural Constraints

- **Concurrency model:** Fully async (`asyncio`) via `redis.asyncio`; no threading. All persistence methods are `async def`. Contextvars (`_context_pipe`, `_action_context`) make the "current pipeline" and "current TTL-refresh batch" implicitly scoped per async task, which is safe under `asyncio` task-local semantics but means these mechanisms would need care if ever adapted to a threaded model.
- **Global mutable state:** `REDIS_MODELS: list[type[AtomicRedisModel]]` (`rapyer/base.py:1077`) is a process-wide, append-only registry populated by every `__init_subclass__` call; `_REGISTERED_SCRIPT_SHAS` (`rapyer/scripts/registry.py:44`) is a process-wide dict of loaded script SHAs. Both are module-level globals with no explicit reset/teardown hook (tests must manage isolation manually, e.g. via fixtures that clear `REDIS_MODELS`).
- **Class-definition-time side effects:** Subclassing `AtomicRedisModel` performs non-trivial work immediately at class-body-execution time (`__init_subclass__`) — including possibly raising `DuplicateModelNameError` — so importing a model module has side effects beyond defining a class.
- **Circular imports (deliberately worked around):** `rapyer/types/base.py` imports from `rapyer/actions.py` (not `rapyer/context.py`) specifically to avoid a cycle (see comment at `rapyer/types/base.py:11`); `rapyer/scripts/registry.py` imports `SpecialFieldType` lazily inside `register_scripts()` to avoid a cycle between `rapyer.types.special` and `rapyer.scripts.constants`; `ForeignKey`/`relational.py` import `AtomicRedisModel` lazily inside functions/methods to avoid `rapyer.base` ↔ `rapyer.types.foreign_key` cycles.
- **Pipeline reuse invariant:** `ensure_pipeline` only ever creates a *new* pipeline if no outer one exists in the current context; nested calls to `ensure_pipeline` inside an active pipeline silently reuse the outer one and never call `.execute()` themselves. Code that calls `ensure_pipeline(..., should_execute=False)` (e.g. `adelete_by_key`) is responsible for executing (or explicitly deferring to the outer caller) — getting this wrong silently drops writes or double-executes.

## Anti-Patterns

### Bypassing `aupdate`/`__setattr__` for special fields

**What happens:** Directly assigning to a special field (`model.my_set = {1,2,3}`) or trying to pass a special-field name into `aupdate(**kwargs)` is guarded against — `aupdate` raises `UpdateAtomicModelError` if any kwarg key is in `_special_field_names`.
**Why it's wrong:** Special fields manage their own separate Redis key and cannot be serialized as a JSON-path `SET`; doing so would silently desync the local Python mirror from the real Redis-side structure.
**Do this instead:** Call the SF's own async methods (`await model.my_set.aadd(x)`, `await model.my_queue.apush(x, priority)`) which route through `self.pipeline`/`self.client` correctly.

### Accessing an unresolved `ForeignKey` attribute synchronously

**What happens:** Code that does `fk.some_field` before calling `await fk.afetch()` raises `NotResolvedError` from `ForeignKey.__getattr__` (`rapyer/types/foreign_key.py:79`).
**Why it's wrong:** Attribute access cannot `await`, so there is no way to transparently fetch on first access; treating the FK as "already the target object" is a common mistake carried over from ORMs with eager/lazy proxy objects that support blocking I/O.
**Do this instead:** Always `await instance.some_fk.afetch()` before reading fields off it, or design read paths to explicitly resolve FKs up front (e.g. via `afind`+manual `afetch` loop) when eager loading is needed — there is no built-in eager-load/`select_related` mechanism.

### Assuming cascade delete on `ForeignKey`

**What happens:** Deleting the referencing or referenced model via `adelete`/`adelete_many` never touches the other side of a `ForeignKey` relationship.
**Why it's wrong:** Unlike relational-DB foreign keys, rapyer's FK is a plain, unenforced key string — there is no referential-integrity or cascade layer at all.
**Do this instead:** Implement cascade/cleanup logic explicitly at the application layer (e.g. fetch dependents via an `Index[...]`-backed query, then `adelete_many` them) if referential cleanup is required.

## Error Handling

**Strategy:** A single-rooted exception hierarchy (`RapyerError`, `rapyer/errors/base.py`) with narrowly-named subclasses raised at the point of violation (missing key, corrupted validation, duplicate model name, unresolved FK, bad filter/argument, script-registration failure). No blanket try/except-and-swallow pattern in the core library except where explicitly documented (`ignore_redis_error=True` on `apipeline`/`_apipeline`).

**Patterns:**
- `KeyNotFound` is raised by `aget`/`aload` when a key is missing, and re-raised/propagated by `afind`(`raise_on_missing=True` when explicit keys were requested) — but `afind_one` and `find`-by-expression callers treat "not found" as an empty/`None` result instead of an exception.
- Redis `NOSCRIPT` errors are handled transparently: `arun_sha`/`_apipeline` catch `NoScriptError`, call `handle_noscript_error` (which re-registers all scripts), and retry once; a second `NoScriptError` is converted to `PersistentNoScriptError` (a real server-side problem, not just a cache miss).
- Pydantic `ValidationError` during `create_redis_model` is caught and logged (`logger.debug`), returning `None` for that record — callers building batches (`afind`, `build_models_from_dumps`) simply skip that entry rather than failing the whole call, unless `raise_on_missing` semantics say otherwise (that only guards *missing* keys, not validation failures).
- "Safe load" fields (`SafeLoad[...]` annotation or `Meta.safe_load_all=True`) catch deserialization (pickle) errors per-field, record the field name into `instance._failed_fields`, log a warning, and set the field to `None` instead of failing the whole model load (`make_pickle_field_serializer`, `rapyer/base.py:110`).

## Cross-Cutting Concerns

**Logging:** Standard library `logging.getLogger("rapyer")` used throughout (`rapyer/base.py:107`); `init_rapyer(logger=...)` lets the application redirect rapyer's logger to its own handlers/level.
**Validation:** Entirely delegated to Pydantic v2 (`model_validate`, `field_validator`, `model_validator`), with a custom `context` dict (`REDIS_DUMP_FLAG_NAME`, `FAILED_FIELDS_KEY`) threaded through to switch (de)serializers between "normal Python" and "Redis wire format" behavior.
**Authentication:** None — rapyer only wraps a `redis.asyncio.Redis` client the application constructs/configures; any Redis AUTH/TLS is the application's/`redis-py`'s concern, out of scope for this library.

---

*Architecture analysis: 2026-07-06*
