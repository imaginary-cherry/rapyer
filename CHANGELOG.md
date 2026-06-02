# Changelog

## [1.3.3]

### ✨ Added

- **`aget_or_create`**: New atomic "get-or-create" primitive exposed both as a module-level helper (`rapyer.aget_or_create(model)`) and as a classmethod (`MyModel.aget_or_create(model)`). The existence check, write, and any special-field save/load happen inside a single registered Lua script — one server-side round-trip, no TOCTOU race between `aexists` and `asave`. Special fields nested inside child models are handled in the same atomic dispatch, and the found branch now also refreshes TTL (the call participates in the `FETCH` action group).

### 🐛 Fixed

- **Nested special fields persisted across all actions**: `asave`, `aduplicate`, `ainsert`, batch creation, and `aget_or_create` now recurse into child models and persist their special fields. Previously only special fields declared directly on the top-level model were saved/copied; special fields nested inside a sub-model were silently dropped.
- **TTL tracks nested special-field keys**: `refresh_ttl`, `refresh_ttl_if_needed`, and `aset_ttl` now expire every special-field key reachable from the model — including those on nested sub-models — instead of only top-level ones.
- **TTL refresh resolves to the root model**: Actions triggered through a nested model or special field now walk back to the root aggregate that owns the Redis key and `Meta.ttl`, so TTL is refreshed on the correct key.
- **Inherited special class field override**: Fixed a bug that caused a field to be classified as a special field even when it was overridden in a subclass

### 🛠️ Technical Improvements

- **Forward refs resolved at import time**: `rapyer/__init__.py` now calls `resolve_forward_refs()` after `AtomicRedisModel` is imported, so `RapyerDeleteResult` and `GetOrCreateResult` are usable without first calling `init_rapyer()`.


## [1.3.2]

### ✨ Added

- **`RedisSet` Type**: New special field type backed by a Redis `SET`, providing unordered, unique-member collections stored under `__rapyer_special__:{model_key}:{field_name}`.
  - Supports generic value types: `tags: RedisSet[str]`, `users: RedisSet[float]`
  - Sync set methods batched in pipeline: `add`, `discard`, `remove`, `clear`, `update`, `difference_update`, `intersection_update`, `symmetric_difference_update`, plus in-place operators (`|=`, `&=`, `-=`, `^=`)
  - Async direct operations: `aadd`, `aadd_many`, `aremove`, `apop` (atomic `SPOP`), `aclear`
  - Async reads: `acontains`, `amembers`, `asize`
  - Multi-set algebra against other `RedisSet` instances: `aunion`, `aintersect`, `adifference`
- **`RapyerSerializationError`**: New error raised when a Redis-aware field receives a value it cannot serialize. `RedisPriorityQueue` now raises it when initialized from an unsupported type instead of silently producing an empty queue.

### 🔄 Changed

- **`mark_actions(version=...)` now takes `MarkVersion` enum**: The `version` parameter changed from string literals (`"v1"`/`"v2"`) to the new `MarkVersion` enum (`MarkVersion.V1`/`MarkVersion.V2`). Callers passing string values must migrate.
- **`MarkVersion.V2` is now the default**: `mark_actions` previously defaulted to `v1` (re-check `Meta.refresh_ttl` against the action group at every call). It now defaults to `MarkVersion.V2` (defer the wrap decision to model class install time and refresh unconditionally at runtime). Built-in Redis types updated accordingly.
- **`Field(exclude=True)` Fields Skip Redis Conversion**: Fields marked with `exclude=True` are no longer rewritten into Redis-aware annotations and are not registered as Redis fields. Use `exclude=True` to keep a field purely Pydantic-managed and out of the Redis JSON document.
- **`AtomicRedisModel.adup()` Now copy with redis as source of truth, not local state.
- **BREAKING change key for special fields**: We fixed the special fields key, this means that models that used Priority Queue in nested model will create a fresh new queue in this version (The PQ is still in Beta)  


### 🛠️ Technical Improvements

- **Special Fields Inside Generic Types**: `BaseRedisType` now exposes `contains_sf_field()` and `queue_special_loads_in_pipeline()` hooks so generic Redis containers (e.g., `RedisList[RedisSet[...]]`) participate in the same pipelined load path as top-level special fields. Loads for nested special fields are batched into the same `JSON.MGET` pipeline rather than being fetched separately.

### 🐛 Fixed
- **Fix multiple special fields in a model**: Fixed a bug that cause key overlap of special fields in the same model.


## [1.3.1]

### 🐛 Fixed

- **`RedisPriorityQueue.asize()` Inside `apipeline()`**: `asize()` will now return value even inside pipeline.

### 🛠️ Technical Improvements

- **Improve runtime for action with no ttl updates**: Actions that dont requires ttl updates are now running less code.
- **Optimize runtime for pipeline actions**: removed duplicated calls in pipeline actions to check if ttl needs to be updated, now we check only once per action group instead of every action.


## [1.3.0]

### ✨ Added

- **`SpecialFieldType` Base Class**: Added abstract base for field types that manage their own separate Redis data structures (e.g., Sorted Sets, Streams). Special fields are not found in the json model and can execute complex logic in atomic actions.
- **`RedisPriorityQueue` Type**: Added a new priority queue field type. Lower priority score = higher precedence.
  - Supports generic value types: `tasks: RedisPriorityQueue[MyModel]`
  - Operations: `apush(value, priority)`, `apush_many(items)`, `apop()`, `apeek()`, `asize()`, `aclear()`, `aitems()`, `aremove(value)`
  - `PriorityQueueItem[T]` dataclass for typed push/list results
  - Stored under `__rapyer_special__:{model_key}:{field_name}`, not inline in the model JSON
- **Per-Action TTL Refresh Strategy**: Introduced `ActionGroup` flag enum and a `@mark_actions` decorator that tags every Redis-touching method with the categories of work it performs. `RedisConfig.refresh_ttl` now accepts both `bool` (legacy behavior) and an `ActionGroup` flag set, so users can scope TTL refresh to specific action categories (e.g., refresh on reads but not on appends).
  - Categories: `READ`, `FETCH`, `CREATE`, `UPDATE`, `APPEND`, `DELETE`, `ERASE`, `ARITHMETIC`
  - Example: `Meta = RedisConfig(ttl=3600, refresh_ttl=ActionGroup.READ | ActionGroup.UPDATE)`
  - Refresh is now dispatched at the outermost decorated action boundary (deduplicated by key), instead of being triggered ad-hoc inside individual methods.
- **`BaseRedisType` Hierarchy**: Introduced a common abstract base (`BaseRedisType`) for all Redis-aware field types, unifying inline `RedisType` fields and separate `SpecialFieldType` fields under one type hierarchy.
- **`UpdateAtomicModelError`**: New error raised when attempting to use `aupdate()` on special fields, which manage their own Redis storage.
- **`InvalidRefreshTtlError`**: New error raised when `refresh_ttl` is configured with `ActionGroup.DELETE` (which can never refresh TTL).
- **`DuplicateModelNameError`**: New error raised when two registered models share the same class name.

### 🛠️ Technical Improvements

- **Centralized TTL Refresh Dispatch**: TTL refresh is no longer scattered across individual methods. The `@mark_actions` decorator opens a per-call action context, registered targets are deduplicated by `model.key`, and a single batched refresh runs at the outermost decorator boundary.
- **`asave` / `ainsert` First-TTL Semantics Preserved**: When `refresh_ttl=False` but a model is being created for the first time, TTL is still set via `EXPIRE NX` so newly-created keys get their initial TTL.
- **`apop` / `apopitem` Cannot Run Inside a Pipeline**: `RedisDict.apop()` and `RedisDict.apopitem()` now always execute against the direct Redis client because their callers need the popped value back at call time. Calling them inside `apipeline()` will execute immediately rather than being batched.


### 💥 Breaking Changes

- **`apipeline()` No Longer Refreshes TTL on Its Own**: Entering and exiting an `apipeline()` context no longer triggers a TTL refresh by itself. TTL is now refreshed only by the actions executed inside the pipeline, according to `refresh_ttl` configuration. A future release will support per-model TTL changes for every model touched in a pipeline.
- **Duplicate Model Class Names Are Rejected**: Registering two `AtomicRedisModel` subclasses with the same `__name__` now raises `DuplicateModelNameError` at class-definition time. Rapyer resolves model classes from Redis keys by `__name__`, so duplicates were already unsafe.
- **`afind()` rejects mixing keys and expressions**: Calling `afind()` with both keys (str) and `Expression` arguments now raises `UnsupportedArgumentValueError` instead of silently ignoring the expressions. Previously this combination logged a warning and dropped the expressions; callers must now choose one mode (keys or filter expressions) per call.
- **`afind_one()` returns `None` for missing keys**: Calling `Model.afind_one(key)` with a key that does not exist in Redis now returns `None` instead of raising `KeyNotFound`. This aligns the classmethod with the module-level `rapyer.afind_one()` and matches the existing behavior for non-matching expressions.
- **`adelete()` raises BadDeleteActionError when try to delete from inner model.



## [1.2.6]

### ✨ Added

- **`aexists()` Method**: Added `aexists()` classmethod to `AtomicRedisModel` to check if a key exists in Redis, returning a boolean.
  - Automatically prepends the class key prefix when using `Key[]` annotation and only a primary key value is provided
  - Supports pipeline context
  - Example: `exists = await User.aexists("user_123")`
- **Global `aexists()` Function**: Added `rapyer.aexists()` function to check key existence without needing the specific model class.
  - Resolves the model class from the key prefix automatically
  - Returns `False` for unknown class prefixes
  - Example: `exists = await rapyer.aexists("UserModel:user_123")`


## [1.2.5]

### ✨ Added

- **`use_existing_pipe` Parameter for `apipeline()`**: Added `use_existing_pipe` flag to both `model.apipeline()` and the global `rapyer.apipeline()` that reuses an existing pipeline from context instead of creating a new one.
  - When `use_existing_pipe=True` and a pipeline already exists in the current context, it yields the existing pipeline instead of nesting a new one
  - Example: `async with model.apipeline(use_existing_pipe=True) as m: await m.asave()`


## [1.2.4]

### 🐛 Fixed

- **Pipeline Operations for Redis Types**: Fixed pipeline using `SET` instead of atomic operations (e.g., `INCRBY`) for Redis-native types. When modifying a `RedisInt` with `+= 5` inside a pipeline, it previously overwrote the value with `SET` instead of using `INCRBY`. Non-Redis-type fields are now correctly updated via pipeline while Redis-native types manage their own updates.

### ✨ Added

- **CodSpeed benchmarks**: Added CodSpeed benchmarks for Redis operations.

## [1.2.3]

### ✨ Added

- **`afind_one()` Method**: Added `afind_one()` classmethod to `AtomicRedisModel` for retrieving a single model instance matching the given criteria.
  - Returns the first matching model or `None` if no match is found
  - Supports keys, expressions, and no-argument usage (returns any single instance)
  - Example: `user = await User.afind_one(User.age >= 30)`
- **`max_results` Parameter for `afind()`**: Added optional `max_results` parameter to `afind()` to limit the number of returned results.
  - Works with all query modes: keys, expressions, and full scan
  - Uses efficient Redis SCAN for key-based limiting and query paging for expression-based limiting
  - Example: `top_5 = await User.afind(User.active == True, max_results=5)`
- **`RapyerKey` as a Model Field Type**: `RapyerKey` can now be used directly as a field type in models, including inside `RedisList[RapyerKey]`, `RedisDict[RapyerKey]`, `list[RapyerKey]`, and `dict[str, RapyerKey]`.
  - Values are stored as plain strings in Redis (no pickling), and deserialized back as `RapyerKey` instances on load
  - Example: `single_key: RapyerKey`, `key_list: RedisList[RapyerKey]`, `key_dict: dict[str, RapyerKey]`

### 🐛 Fixed

- **Serialization for Nested Generic Types**: Fixed Pydantic schema generation for generic Redis types (e.g., `RedisList[RapyerKey]`, `RedisDict[RapyerKey]`) to correctly preserve inner type arguments during serialization.


## [1.2.2]

### ✨ Added

- **`RapyerKey` Type**: From now on, the key value will be of type `RapyerKey`, RapyerKey is still a string, but now you can identify the string as rapyer key by type.
- **Delete with Expressions**: `Model.adelete_many()` now supports filter expressions, allowing bulk deletion of models matching specific criteria.
  - Example: `await Model.adelete_many(Model.age > 30, Model.active == False)`
- **Global `adelete_many()`**: Added `rapyer.adelete_many()` function to delete models of different types in a single bulk operation.
  - Accepts both string keys and model instances of any type
  - Example: `result = await rapyer.adelete_many(model2.key, order_instance)`

### 🛠️ Technical Improvements

- **Optimized `aduplicate_many()`**: The `aduplicate_many()` method now uses bulk `ainsert()` instead of individual `asave()` calls for better performance.


## [1.2.1]

### ✨ Added

- **Global `rapyer.apipeline()` Function**: Added a global `apipeline()` context manager that enables batched Redis operations across multiple models without requiring a specific model instance.

### 🐛 Fixed
- **Nested Pipeline Support**: Pipelines can now be properly nested, with each pipeline executing its commands independently when exiting its context.
  - Inner pipelines commit changes when they exit, while outer pipeline changes remain pending until the outer context exits
- **Atmoic mocdel field assignments in Pipeline**: Fixed `__setattr__` to check all model fields (including inherited fields) instead of only the current class's annotations, ensuring proper field handling for inherited models.
- **Bug when apipeline raises an error**: Fix an error when apipeline failed that causes future redis action to have no effect 

### 🛠️ Technical Improvements

- **Pipeline Support for `asave()`**: The `asave()` method now works correctly within pipeline context, allowing batched save operations.
  - Example: `async with model.apipeline() as m: await m.asave()`

- **NOSCRIPT Error Recovery for Async Operations**: Recover scripts for redis action when script was deleted (for apop and apop_item functions). 


## [1.2.0]

### 🔄 Changed

- **BREAKING - Removed Deprecated Methods**: Removed all deprecated methods that were marked for removal in 1.2.0:
  - `save()` → use `asave()`
  - `load()` → use `aload()`
  - `delete()` → use `adelete()`
  - `get()` → use `aget()`
  - `duplicate()` → use `aduplicate()`
  - `duplicate_many()` → use `aduplicate_many()`
  - `delete_by_key()` → use `adelete_by_key()`
  - `lock()` → use `alock()`
  - `lock_from_key()` → use `alock_from_key()`
  - `pipeline()` → use `apipeline()`
  - `increase()` → use `aincrease()`

- **BREAKING - Removed Backward Compatibility for Pickled JSON Fields**: Removed backward compatibility for loading old pickled data in JSON-serializable fields. Data must now be in JSON format.

- **Renamed `ignore_if_deleted` to `ignore_redis_error`**: The `apipeline()` parameter `ignore_if_deleted` has been renamed to `ignore_redis_error` for better accuracy.

### 🐛 Fixed

- **Dict Operations Edge Case**: Fixed an edge case where dict operations would fail when the model reference was None.

### 🛠️ Technical Improvements

- **BREAKING - Lua Scripts for Dict Operations**: Extracted `pop()` and `popitem()` dict operations into registered Lua scripts for better maintainability and NOSCRIPT error recovery, these functions will no longer work without init_rapyer setup.
  - Added `dict_pop` and `dict_popitem` scripts to the script registry.
  - Added `arun_sha()` function for executing registered scripts outside pipeline context.

- **Pipeline Transactions for `aupdate()`**: The `aupdate()` method now uses Redis MULTI/EXEC transactions for atomic execution.

- **Pipeline Support for `aset_ttl()`**: The `aset_ttl()` method now works correctly within pipeline context.


## [1.1.7]

### ✨ Added

- **Global `rapyer.afind()` Function**: Added `rapyer.afind()` function to retrieve multiple models of different types by their keys in a single bulk operation.
  - Supports fetching models of heterogeneous types in one call
  - Automatically refreshes TTL for models with `refresh_ttl` enabled
  - Raises `KeyNotFound` if any key is missing in Redis
  - Raises `RapyerModelDoesntExistError` if a key refers to an unregistered model class
  - Example: `models = await rapyer.afind("UserModel:123", "OrderModel:456")`

- **Pipeline Operations for Non-Redis-Native Types**: Added full pipeline support for `List[Any]` and `Dict[str, Any]` fields that store serialized data.
  - Supports `append()`, `extend()`, `insert()`, index assignment for lists
  - Supports `update()`, key assignment, `pop()` for dicts
  - Direct field assignment within pipeline context (e.g., `redis_model.field = value`)
  - All operations are atomic and only committed when the pipeline exits
  - Example: `async with model.apipeline() as m: m.mixed_list.append({"key": "value"})`

- **Enhanced Pipeline Operations for Redis-Native Types**: Added in-place arithmetic operations (`+=`, `-=`) within pipeline context for Redis-native types.
  - `RedisDatetime` and `RedisDatetimeTimestamp`: Support `+=` and `-=` with `timedelta` for atomic date arithmetic
  - `RedisFloat`: Support `+=`, `-=`, `*=`, `/=` for atomic numeric operations
  - `RedisInt`: Support `+=`, `-=` for atomic increment/decrement operations
  - `RedisStr`: Support `+=` for atomic string append operations

- **FakeRedis Support**: Added support for `fakeredis` library for unit testing without a real Redis instance.
  - Supports `rapyer.afind()`, `rapyer.ainsert()`, `rapyer.aget()` with FakeRedis
  - Supports pipeline operations with FakeRedis
  - Enables faster test execution without Redis dependency

### 🐛 Fixed

- **TTL Support in `ainsert`**: The `ainsert()` method now automatically sets TTL on inserted models based on their model configuration.

### 🔄 Changed

- **`Model.afind()` Strict Key Validation**: When specific keys are passed to `Model.afind()`, it now raises `KeyNotFound` if any key is missing in Redis. Previously, missing keys were silently ignored.

## [1.1.6]

### ✨ Added

- **afind Key-Based Search**: Added support for passing keys directly to `afind()` to retrieve specific models by their keys, without requiring a Redis Search query.
  - Supports both full keys (`Model:uuid`) and primary key values (`uuid`)
  - Example: `await Model.afind(key1, key2)` or `await Model.afind("uuid1", "uuid2")`
  - Note: If both keys and expressions are provided, expressions are ignored with a warning
- **Logger Configuration in init_rapyer**: Added `logger` parameter to `init_rapyer()` function to configure the rapyer logger with a custom logger's level and handlers.
  - Example: `await init_rapyer(redis=redis_client, logger=my_logger)`
- **aset_ttl Method**: Added `aset_ttl(ttl)` method to `AtomicRedisModel` for manually setting or updating the TTL of a model instance.
  - Example: `await model.aset_ttl(3600)` sets TTL to 1 hour
  - Only works on top-level models (raises `RuntimeError` if called on inner models)

### 🐛 Fixed

- **afind with Non-JSON Keys**: Fixed `afind` to gracefully skip non-JSON keys (e.g., lock keys like `Model:key:lock`) that match the model's key pattern but contain plain string values instead of JSON.
- **afind with Invalid JSON Schema**: Fixed `afind` to skip entries with JSON values that don't match the model schema, preventing validation errors from crashing the entire operation.
- **Global afind Bug**: Fixed a bug where `afind` would fail when encountering keys that were deleted during the operation.
- **apipeline bug**: Fixed a bug for apipeline when we want to ignore deleted model.


## [1.1.5]

### ✨ Added

- **RedisList.remove_range()**: Added `remove_range(start, end)` method to `RedisList` for removing a range of items (like `del list[start:end]`).
  - Works within pipeline context for atomic operations
  - Supports negative indices (count from end)
  - Uses Lua script internally for race-condition-free execution
  - Example: `playlist.songs.remove_range(1, 3)` removes items at indices 1 and 2
- **SafeLoad Field Annotation**: Added `SafeLoad[T]` annotation for fields that should gracefully handle deserialization failures instead of raising exceptions.
  - When a SafeLoad field fails to deserialize, it returns `None` and logs a warning instead of crashing
  - Failed field names are tracked in the model's `failed_fields` property
  - Example: `safe_type_field: SafeLoad[Optional[Type[str]]] = Field(default=None)`
- **Model-Wide SafeLoad Configuration**: Added `safe_load_all` option to `RedisConfig` Meta class to treat all non-Redis-supported fields as SafeLoad fields.
  - Example: `Meta = RedisConfig(safe_load_all=True)`

### 🛠️ Technical Improvements

- **Pipeline Transactions**: Pipelines now use Redis MULTI/EXEC transactions for atomic execution of batched operations.
- **NOSCRIPT Error Recovery**: Pipelines automatically recover from NOSCRIPT errors (e.g., after Redis restart) by re-registering Lua scripts and retrying failed script commands.
- **Smart Field Serialization**: Fields that can be JSON-serialized are now stored as native JSON instead of being pickled. This improves Redis data readability and interoperability with other systems.
  - Pickle is only used for fields that cannot be JSON-serialized (e.g., `type` objects, custom classes)
  - Backward compatible: existing pickled data is automatically detected and loaded correctly, We will remove the compatibility in version 1.2.0 


## [1.1.4]
### ✨ Added
- **Global alock_from_key Function**: Added `rapyer.alock_from_key()` function to create locks without needing a model instance. This allows locking by key directly for operations that don't require the model class.
- **Model TTL Extension on Redis Actions**: Models now automatically extend their TTL when performing Redis actions, keeping frequently accessed models alive longer.

### 🔧 Improved
- **Redis Locking Mechanism**: Now using formal Redis lock for more persistent and reliable locking mechanism.

### 🐛 Fixed
- **apipeline KeyNotFound**: Fixed `apipeline` for cases where model doesn't exists in redis.
- **rapyer.get**: Fix a bug in the rapyer.get() function.
- **Context Manager Annotations**: Fixed type annotations for context managers to properly reflect their return types.
- **RedisBytes Pipeline**: Fixed bug in RedisBytes when used within pipeline context.
- **RedisList Pipeline**: Fixed bug in RedisList when used within pipeline context.
- **afind Nested Fields**: Fixed `afind` to support filtering on nested fields (e.g., `afind(User.parent.age > 20)`).
- **Key and Index Type Checking**: Fixed type checking support for `Key[T]` and `Index[T]` annotations. IDEs now correctly recognize `Index[str]` as `str` instead of `_IndexType[str]`.

### 🛠️ Technical Improvements
- **Test Coverage**: Added tests for full coverage.

## [1.1.3]
Reupload of 1.1.2 

## [1.1.2]
We yanked the 1.1.1 release due to a bug in the pipeline context manager.
This is the fixed version.

## [1.1.1]
In this version we officaly starting the support for bulk operation on multiple models. In line with our philsophy of atomic operations.

### ✨ Added
- **Bulk Insert**: We added the ainsert classmethod to AtomicRedisModel to insert multiple models in a single operation. 
- **Bulk delete**: We added the adelete_many classmethod to AtomicRedisModel to delete many objects in a single operation.
- **Flexible Bulk Delete**: The adelete_many method now supports both model instances and Redis keys as arguments, allowing for more flexible bulk deletion operations. You can mix and match models and keys in a single call.
- **RedisFloat Type**: Added support for float Redis types with atomic increment operations and in-place arithmetic operations (+=, -=, *=, /=) within pipeline contexts.
- **Global ainsert Function**: Added `rapyer.ainsert()` function to insert models of any type in a single operation, enabling bulk inserts of heterogeneous model types.
- **Filtering in Search**: Added support for filtering in `afind()` method using expressions, allowing you to search for models that match specific criteria with operators like ==, !=, >, <, >=, <= and logical operators (&, |, ~).
- **RedisDatetimeTimestamp Type**: Added new `RedisDatetimeTimestamp` type that stores datetime values as timestamps (floats) in Redis instead of ISO strings. This provides more efficient storage and better compatibility with external systems that expect timestamp format. Note: timezone information is lost during conversion as timestamps represent UTC moments in time.

### ⚠️ Deprecated
- **Function Name Migration to Async**: The following functions have been renamed to follow async naming conventions. We moved to a strict convention to support non async models in a future version. Old names are deprecated and will be removed in a future version:
  - `save()` → `asave()` - Save model instance to Redis
  - `load()` → `aload()` - Load model data from Redis  
  - `delete()` → `adelete()` - Delete model instance from Redis
  - `get()` → `aget()` - Retrieve model instance by key (class method)
  - `duplicate()` → `aduplicate()` - Create a duplicate of the model
  - `duplicate_many()` → `aduplicate_many()` - Create multiple duplicates
  - `delete_by_key()` → `adelete_by_key()` - Delete model by key (class method)
  - `lock()` → `alock()` - Create lock context manager for model
  - `lock_from_key()` → `alock_from_key()` - Create lock context manager from key (class method)
  - `pipeline()` → `apipeline()` - Create pipeline context manager for batched operations 

## [1.1.0]

### ✨ Added
- **Version Support**: Support more python versions, pydantic and redis versions, including tests in pipeline for each version.

### 🐛 Fixed
- **Rapyer init**: Fix a bug for init_rapyer when using url.

### 🔄 Changed
- **BREAKING**: We stopped using RedisListType, RedisIntType, etc. instead, you can use RedisList directly with full IDE support.

## [1.0.4]

### ✨ Added

- **In-Place Pipeline Changes**: Added support for in-place pipeline operations for all Redis types
  - Any action performed on Redis models within a pipeline now directly affects the Redis model instance
  - Both awaitable and non-awaitable functions now support in-place modifications during pipeline execution
- **Support for generic fields for dict and list**: List and Dict now support any serializable type as a genric type
- **Model afind**: We added afind function to extract all models of a specific class. In the future, we will also add options to use filters in the afind

## [1.0.3]

### ✨ Added

- **Custom Primary Keys**: Added `Key` annotation to specify custom fields as primary keys instead of auto-generated ones
- **Enhanced IDE Typing Support**: Added specialized Redis types (`RedisListType`, `RedisDictType`, etc.) for better IDE autocompletion and type hinting
- **Global Model Retrieval**: Added `rapyer.get()` function to retrieve any Redis model instance by its key without needing to know the specific model class
  - Example: `model = await rapyer.get("UserModel:12345")`
- **Model Discovery**: Added `find_redis_models()` function to discover all Redis model classes in the current environment
- **Key Discovery**: Added `find_keys()` class method to retrieve all Redis keys for a specific model class

## [1.0.2] - 2025-11-05

### ✨ Added

- **Inheritance Model Support**: Added support for inheritance models - models that inherit from a Redis model still create a Redis model with full functionality
- **Global Configuration**: Added `init_rapyer()` function to set Redis client and TTL for all models at once
  - Accepts Redis client instance or connection string (e.g., `"redis://localhost:6379"`)
  - Allows setting global TTL for all Redis models
  - Example: `init_rapyer(redis="redis://localhost:6379", ttl=3600)`
- **Atomic Updates**: Added `aupdate()` method to AtomicRedisModel for selective field updates without loading the entire model
  - Enables direct field updates in Redis: `await model.aupdate(field1="value", field2=123)`
  - Maintains type safety and validation during updates
  - Uses Redis JSON path operations for efficient field-only updates
  - All field updates in a single aupdate call are atomic

### 🐛 Fixed

- **Redis Type Override Bug**: Fixed a bug that overrode the Redis type in lock and pipeline operations
- **Redis List Bug**: Fixed a bug for extending an empty list

### ⚠️ Compatibility Notice

- **Pydantic Version Constraint**: This version supports Pydantic up to 2.12.0 due to internal logic changes in newer versions
- A future release will include support for multiple Pydantic versions
- All previous versions also have the same Pydantic 2.12.0 limitation

## [1.0.1] - 2025-11-04

### ✨ Added

- **Non-Serializable Type Support**: Added support for non-serializable types (like `type` and other pickleable objects)
- **Pickle Storage**: Non-serializable types are now stored in Redis as pickle data for proper serialization
- **Optional Field Support**: Added support for optional fields in Redis types

## [1.0.0] - 2025-11-02

### 🚀 Major Changes - Native BaseModel Integration

This release introduces **native BaseModel compatibility**, making Redis types work seamlessly with Pydantic models without requiring explicit initialization.

### ✨ Added

- **Native Redis Type Integration**: Redis types now work directly with BaseModel - no need to initialize with `""`, `0`, etc.
- **Direct Field Assignment**: Use simple assignment like `name: RedisStr = ""` instead of `name: RedisStr = ""`
- **Enhanced Nested Operations**: Support for saving inner fields directly with `model.lst[1].asave()`
- **Simplified Type Declarations**: All Redis types (RedisStr, RedisInt, RedisList, RedisDict, RedisBytes) now support native Python value assignment

### 🔄 Changed

- **BREAKING**: Removed `set()` function - Redis types now update automatically when modified
- **Simplified API**: Redis type actions now automatically update the Redis store

### 🛠️ Technical Improvements

- Streamlined type validation and serialization
- Improved IDE support for Redis types with native Python syntax
- Better integration with Pydantic's validation system
- Reduced boilerplate code for Redis type usage
