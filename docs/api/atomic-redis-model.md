# API Reference

This page provides a comprehensive reference of all available functions and methods in the Rapyer package.

## AtomicRedisModel

The `AtomicRedisModel` is the core class that all Redis-backed models inherit from. It provides atomic operations and seamless integration with Redis as a backend storage.

### Properties

#### `pk`
**Type:** `str`  
**Description:** Primary key of the model. If a key field is defined using `KeyAnnotation`, returns that field's value; otherwise returns the internal UUID.

```python
user = User(name="John", age=30)
print(user.pk)  # Returns UUID if no key field defined
```

#### `key`
**Type:** `str`  
**Description:** The Redis key used to store this model instance. Format: `{ClassName}:{pk}`

```python
user = User(name="John")
print(user.key)  # "User:abc-123-def-456"
```

#### `field_name`
**Type:** `str`  
**Description:** The field name when this model is used as a nested field in another model.

#### `field_path`
**Type:** `str`  
**Description:** The full JSON path to this model when nested, including parent paths.

#### `json_path`
**Type:** `str`  
**Description:** The JSON path used for Redis JSON operations. Returns `"$"` for root level or `"${field_path}"` for nested models.

### Instance Methods

#### `asave()`
**Type:** `async` method  
**Returns:** `Self`  
**Description:** Saves the current model instance to Redis using JSON.SET operation.

```python
user = User(name="John", age=30)
await user.asave()
```

#### `aload()`
**Type:** `async` method
**Returns:** `Self`
**Raises:** `CantSerializeRedisValueError` if the value in Redis cannot be deserialized (Corruption or missing resources)
**Description:** Loads the latest data from Redis for this model instance, updating the current instance.

```python
await user.aload()  # Refreshes user with latest Redis data
```

#### `adelete()`
**Type:** `async` method  
**Returns:** `bool`  
**Description:** Deletes this model instance from Redis. Can only be called on top-level models (not nested ones).

```python
success = await user.adelete()
```

#### `aset_ttl(ttl)`
**Type:** `async` method
**Parameters:**
- `ttl` (int): Time-to-live in seconds
**Description:** Sets the TTL for this model instance in Redis. Can only be called on top-level models. Supports pipeline context for atomic TTL updates.

```python
# Direct usage
await user.aset_ttl(3600)  # Expire in 1 hour

# Within pipeline context
async with user.apipeline():
    user.score += 100
    await user.aset_ttl(7200)
    await user2.aset_ttl(7200)  # TTL set atomically with other changes as part of the transaction
```

#### `aduplicate()`
**Description:** Creates a duplicate of the current model with a new primary key and saves it to Redis.

```python
user_copy = await user.aduplicate()
```

#### `aduplicate_many(num)`
**Type:** `async` method  
**Parameters:** 
- `num` (int): Number of duplicates to create  
**Returns:** `list[Self]`  
**Description:** Creates multiple duplicates of the current model.

```python
user_copies = await user.aduplicate_many(5)  # Creates 5 duplicates
```

#### `update(**kwargs)`
**Type:** Synchronous method  
**Parameters:** 
- `**kwargs`: Field values to update  
**Description:** Updates model fields locally (does not save to Redis).

```python
user.update(name="Jane", age=25)
```

#### `aupdate(**kwargs)`
**Type:** `async` method  
**Parameters:** 
- `**kwargs`: Field values to update  
**Description:** Updates specified fields both locally and in Redis atomically.

```python
await user.aupdate(name="Jane", age=25)
```

#### `is_inner_model()`
**Type:** Synchronous method  
**Returns:** `bool`  
**Description:** Returns True if this model is a nested field within another model.

```python
if user.is_inner_model():
    print("This is a nested model")
```

### Class Methods

#### `aget(key)`
**Type:** `async` class method
**Parameters:**
- `key` (str): The Redis key to retrieve
**Returns:** `Self`
**Raises:**

- `KeyNotFound` if key doesn't exist
- `CantSerializeRedisValueError` if the value in Redis cannot be deserialized  (Corruption or missing resources)

**Description:** Retrieves a model instance from Redis by its key.

```python
user = await User.aget("User:abc-123")
```

#### `adelete_by_key(key)`
**Type:** `async` class method  
**Parameters:** 
- `key` (str): The Redis key to delete  
**Returns:** `bool`  
**Description:** Deletes a model from Redis by its key without needing to load it first.

```python
success = await User.adelete_by_key("User:abc-123")
```

#### `afind(*args)`
**Type:** `async` class method
**Parameters:**
- `*args` (str | Expression): Keys (strings) or filter expressions
**Returns:** `list of redis models`
**Raises:** `CantSerializeRedisValueError` if a value in Redis cannot be deserialized  (Corruption or missing resources)
**Description:** Retrieves model instances from Redis. Supports three modes:

1. **No arguments** - Returns all instances
2. **Keys** - Pass string keys to retrieve specific models
3. **Expressions** - Pass filter expressions (requires `Index` annotation)

!!! note
    Keys and expressions are mutually exclusive. If both are provided, keys take priority and expressions are ignored (a warning is logged).

**Supported Filter Operators:**
- `==` - Equal to
- `!=` - Not equal to
- `>` - Greater than
- `<` - Less than
- `>=` - Greater than or equal to
- `<=` - Less than or equal to
- `&` - Logical AND
- `|` - Logical OR
- `~` - Logical NOT

```python
# Get all users
all_users = await User.afind()

# Find by keys (full key or just primary key)
users = await User.afind("User:abc123", "User:def456")
users = await User.afind("abc123", "def456")  # prefix added automatically

# Filter with expressions (requires Index annotation on fields)
active_users = await User.afind(User.status == "active")
adult_users = await User.afind(User.age >= 18)

# Complex filters
filtered = await User.afind(
    (User.age > 18) & (User.status == "active") | (User.role == "admin")
)
```

#### `afind_keys()`
**Type:** `async` class method  
**Returns:** `list[str]`  
**Description:** Retrieves all Redis keys for instances of this model class.

```python
user_keys = await User.afind_keys()  # Returns ["User:123", "User:456", ...]
```

#### `ainsert(*models)`
**Type:** `async` class method  
**Parameters:** 
- `*models` (Self): Variable number of model instances to insert  
**Returns:** `None`  
**Description:** Inserts multiple model instances to Redis in a single atomic transaction. This is significantly more efficient than calling `save()` on each model individually, as it uses Redis pipelining to batch all operations.

**Benefits:**
- **Transactional**: All models are saved atomically - either all succeed or all fail
- **Performance**: Uses a single Redis pipeline instead of multiple round trips
- **Network Efficiency**: Reduces network latency by batching operations
- **Consistency**: Prevents partial saves if an error occurs during bulk operations

```python
# Create multiple user instances
users = [
    User(name="Alice", email="alice@example.com"),
    User(name="Bob", email="bob@example.com"),
    User(name="Charlie", email="charlie@example.com")
]

# Insert all users atomically
await User.ainsert(*users)

# Alternative syntax
await User.ainsert(user1, user2, user3)
```

#### `adelete_many(*args)`
**Type:** `async` class method  
**Parameters:** 
- `*args` (Self | str): Variable number of model instances or Redis keys to delete   
**Description:** Deletes multiple model instances from Redis in a single atomic transaction. Accepts both model instances and Redis key strings, making it flexible for different use cases. This is significantly more efficient than calling `delete()` on each model individually, as it uses Redis batch deletion.

```python
# Delete using model instances
await User.adelete_many(*users)

# Delete using Redis keys
await User.adelete_many("User:123", "User:456", "User:789")

# Mix models and keys
await User.adelete_many(user1, "User:xyz", user2.key, user3)

# Delete all instances of a model
all_users = await User.afind()
await User.adelete_many(*all_users)
```

#### `class_key_initials()`
**Type:** Class method  
**Returns:** `str`  
**Description:** Returns the class name used as the key prefix. Override to customize key naming.

```python
class User(AtomicRedisModel):
    @classmethod
    def class_key_initials(cls):
        return "USR"  # Keys will be "USR:pk" instead of "User:pk"
```

### Context Managers

#### `alock_from_key(key, action="default", save_at_end=False)`
**Type:** `async` context manager  
**Parameters:**
- `key` (str): Redis key to lock
- `action` (str): Lock action name for different operation types
- `save_at_end` (bool): Whether to save changes when context exits  
**Returns:** `AsyncGenerator[Self, None]`  
**Description:** Acquires an exclusive lock on the model and yields the loaded instance.

```python
async with User.alock_from_key("User:123", "profile_update", save_at_end=True) as user:
    user.name = "Updated Name"
    # Automatically saved when context exits
```

#### `alock(action="default", save_at_end=False)`
**Type:** `async` context manager  
**Parameters:**
- `action` (str): Lock action name
- `save_at_end` (bool): Whether to save changes when context exits  
**Returns:** `AsyncGenerator[Self, None]`  
**Description:** Acquires an exclusive lock on the current model instance.

```python
async with user.alock("settings_update", save_at_end=True) as locked_user:
    locked_user.settings = {"theme": "dark"}
```

#### `apipeline(ignore_redis_error=False)`
**Type:** `async` context manager  
**Parameters:**
- `ignore_redis_error` (bool): Continue if model was deleted during pipeline  
**Returns:** `AsyncGenerator[Self, None]`  
**Description:** Batches all operations into a Redis pipeline for atomic execution.

```python
async with user.apipeline() as pipeline_user:
    user.score += 100
    user.achievements.append("New Achievement")
    # All operations executed atomically
```

### Configuration

#### `Meta`
**Type:** `ClassVar[RedisConfig]`  
**Description:** Configuration class for Redis connection settings and model behavior.

```python
class User(AtomicRedisModel):
    name: str
    age: int

    Meta = RedisConfig(redis=redis_client, ttl=3600)  # Expire after 1 hour
```

**Available options:**

- `redis` - Redis client instance
- `ttl` - Time-to-live in seconds
- `refresh_ttl` - Refresh TTL on read/write (default: `True`)
- `safe_load_all` - Treat all non-Redis fields as SafeLoad (default: `False`)
- `prefer_normal_json_dump` - Use JSON serialization for compatible fields instead of pickle (default: `False`)

### Special Behaviors

#### Key Field Definition
Use `KeyAnnotation` to specify which field should be used as the primary key:

```python
from rapyer.fields import KeyAnnotation
from typing import Annotated

class User(AtomicRedisModel):
    username: Annotated[str, KeyAnnotation] 
    email: str
    
user = User(username="john_doe", email="john@example.com")
print(user.pk)   # "john_doe"
print(user.key)  # "User:john_doe"
```

#### Automatic Redis Type Conversion
Model fields are automatically converted to Redis-compatible types:

```python
class User(AtomicRedisModel):
    name: str          # Becomes RedisStr
    tags: List[str]    # Becomes RedisList[str]
    settings: Dict[str, str]  # Becomes RedisDict[str, str]
```

#### Field Linking
Redis type fields are automatically linked to their parent model for proper key resolution:

```python
user = User(name="John", tags=["python", "redis"])
print(user.tags.key)  # "User:abc-123.tags"
```

### Error Handling

#### `KeyNotFound`
Raised when attempting to get or load a model that doesn't exist in Redis:

```python
from rapyer.errors import KeyNotFound

try:
    user = await User.aget("User:nonexistent")
except KeyNotFound:
    print("User not found in Redis")
```

### Example Usage

```python
from rapyer import AtomicRedisModel
from typing import List, Dict


class User(AtomicRedisModel):
    name: str
    email: str
    age: int = 0
    tags: List[str] = []
    settings: Dict[str, str] = {}


# Create and save
user = User(name="John", email="john@example.com", age=30)
await user.asave()

# Retrieve
retrieved_user = await User.aget(user.key)

# Update atomically
await user.aupdate(age=31, tags=["python", "redis"])

# Batch operations
async with user.apipeline():
    user.age += 1
    user.tags.append("asyncio")
    user.settings["theme"] = "dark"

# Lock for exclusive access
async with user.alock("profile_update", save_at_end=True):
    if user.age >= 25:
        user.tags.append("adult")
        user.settings["account_type"] = "premium"
```