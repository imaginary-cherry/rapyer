# Changelog

## [1.1.4]
### ✨ Added
- **Global alock_from_key Function**: Added `rapyer.alock_from_key()` function to create locks without needing a model instance. This allows locking by key directly for operations that don't require the model class.

### 🔧 Improved
- **Redis Locking Mechanism**: Now using formal Redis lock for more persistent and reliable locking mechanism.

### 🐛 Fixed
- **rapyer.get**: Fix a bug in the rapyer.get() function.
- **Context Manager Annotations**: Fixed type annotations for context managers to properly reflect their return types.
- **RedisBytes Pipeline**: Fixed bug in RedisBytes when used within pipeline context.
- **RedisList Pipeline**: Fixed bug in RedisList when used within pipeline context.

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
