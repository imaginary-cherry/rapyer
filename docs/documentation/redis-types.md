# Redis Types

## Automatic Type Conversion

**AtomicRedisModel automatically converts all types to their Redis equivalents recursively**, providing seamless atomic operations without changing your code. This conversion happens transparently:

- `list` → `RedisList` 
- `dict` → `RedisDict`
- `str` → `RedisStr`  
- `int` → `RedisInt`
- `float` → `RedisFloat`
- `bytes` → `RedisBytes`
- `datetime` → `RedisDatetime` (or `RedisDatetimeTimestamp` for timestamp storage)
- `BaseModel` → `AtomicRedisModel` (nested models)

**This is completely seamless** - since `RedisList` inherits from `list`, `RedisDict` inherits from `dict`, etc., your existing code continues to work exactly as before, but now with atomic Redis operations available.

```python
class User(AtomicRedisModel):
    name: str           # Automatically becomes RedisStr
    age: int            # Automatically becomes RedisInt  
    tags: List[str]     # Automatically becomes RedisList[str]
    settings: Dict[str, str]  # Automatically becomes RedisDict[str, str]

# Use exactly like regular Python types
user = User(name="Alice", age=25, tags=["python"], settings={"theme": "dark"})

# But now atomic Redis operations are available
await user.tags.aappend("redis")  # Atomic list append
await user.settings.aupdate(language="en")  # Atomic dict update
```

## Type System Overview

Rapyer's type system provides seamless integration between Python types and Redis operations through automatic conversion. Whether you use standard Python types or explicit Redis types, you get the same powerful atomic operations while maintaining full compatibility with your existing code.

## RedisStr

**Inherits from:** `str`, `RedisType`  
**Redis Storage:** Native string values  
**Use Case:** Text data that benefits from atomic operations

```python
from rapyer.types import RedisStr  # Recommended: TypeAlias 
# from rapyer.types import RedisStr     # Alternative: Direct class

class User(AtomicRedisModel):
    name: RedisStr = ""              # Flexible typing with union support
    status: RedisStr = "active"      # Accepts both str and RedisStr
```

### Available Operations

| Operation | Method | Description |
|-----------|---------|-------------|
| **save** | `await user.name.asave()` | Save field value to Redis |
| **load** | `await user.name.aload()` | Load field value from Redis (returns value, doesn't update model) |

All standard `str` methods are available (upper, lower, strip, etc.) but operate on the local copy.

---

## RedisInt

**Inherits from:** `int`, `RedisType`  
**Redis Storage:** Integer numeric values with atomic increment support  
**Use Case:** Counters, IDs, scores, and integer numeric data requiring atomic updates

```python
from rapyer.types import RedisInt  # Recommended: TypeAlias
# from rapyer.types import RedisInt     # Alternative: Direct class

class Counter(AtomicRedisModel):
    count: RedisInt = 0              # Flexible typing with union support
    score: RedisInt = 100            # Accepts both int and RedisInt
```

### Available Operations

| Operation     | Method                             | Description |
|---------------|------------------------------------|-------------|
| **save**      | `await counter.count.asave()`      | Save field value to Redis |
| **load**      | `await counter.count.aload()`      | Load field value from Redis (returns value, doesn't update model) |
| **aincrease** | `await counter.count.aincrease(5)` | Atomically increment by amount (default: 1) |

!!! warning "Non-mutating Operation"
    The `increase()` method returns the new value from Redis but **does not update the local instance**. You need to reload the model or field to see the updated value locally.

---

## RedisFloat

**Inherits from:** `float`, `RedisType`  
**Redis Storage:** Floating-point numeric values with atomic increment support  
**Use Case:** Prices, ratings, percentages, and decimal data requiring atomic updates

```python
from rapyer.types import RedisFloat  # Recommended: TypeAlias
# from rapyer.types import RedisFloat     # Alternative: Direct class

class Product(AtomicRedisModel):
    price: RedisFloat = 0.0           # Flexible typing with union support
    rating: RedisFloat = 5.0          # Accepts both float and RedisFloat
```

### Available Operations

| Operation     | Method | Description |
|---------------|---------|-------------|
| **save**      | `await product.price.asave()` | Save field value to Redis |
| **load**      | `await product.price.aload()` | Load field value from Redis (returns value, doesn't update model) |
| **aincrease** | `await product.price.aincrease(1.5)` | Atomically increment by amount (default: 1.0) |

!!! warning "Non-mutating Operation"
    The `aincrease()` method returns the new value from Redis but **does not update the local instance**. You need to reload the model or field to see the updated value locally.

---

## RedisList

**Inherits from:** `list[T]`, `GenericRedisType[T]`  
**Redis Storage:** JSON arrays with full list operation support  
**Use Case:** Collections, queues, and ordered data requiring atomic list operations

```python
from rapyer.types import RedisList  # Recommended: TypeAlias
# from rapyer.types import RedisList     # Alternative: Direct class

class UserProfile(AtomicRedisModel):
    tags: RedisList[str] = Field(default_factory=list)    # Flexible typing with union support
    scores: RedisList[int] = Field(default_factory=list)  # Accepts both list[int] and RedisList[int]
```

### Available Operations

| Operation | Method | Description |
|-----------|---------|-------------|
| **save** | `await user.tags.asave()` | Save entire list to Redis |
| **load** | `await user.tags.aload()` | Load entire list from Redis (returns value, doesn't update model) |
| **append** | `await user.tags.aappend("python")` | Atomically append single item |
| **extend** | `await user.tags.aextend(["redis", "async"])` | Atomically append multiple items |
| **insert** | `await user.tags.ainsert(0, "first")` | Atomically insert at index |
| **pop** | `item = await user.tags.apop()` | Atomically remove and return item |
| **clear** | `await user.tags.aclear()` | Atomically clear entire list |

Standard `list` methods (append, extend, insert, clear) work on both local copy and Redis when used with pipelines. Use async methods (apop, etc.) for operations that require returning values.

---

## RedisDict

**Inherits from:** `dict[str, T]`, `GenericRedisType[T]`  
**Redis Storage:** JSON objects with full dictionary operation support  
**Use Case:** Key-value mappings, settings, and structured data requiring atomic updates

```python
from rapyer.types import RedisDict  # Recommended: TypeAlias
# from rapyer.types import RedisDict     # Alternative: Direct class

class UserSettings(AtomicRedisModel):
    preferences: RedisDict[str, str] = Field(default_factory=dict)  # Flexible typing with union support
    metadata: RedisDict[str, int] = Field(default_factory=dict)     # Accepts both dict and RedisDict
```

### Available Operations

| Operation | Method | Description |
|-----------|---------|-------------|
| **save** | `await user.preferences.asave()` | Save entire dict to Redis |
| **load** | `await user.preferences.aload()` | Load entire dict from Redis (returns value, doesn't update model) |
| **update** | `await user.preferences.aupdate(theme="dark")` | Atomically update multiple keys |
| **set item** | `await user.preferences.aset_item("lang", "en")` | Atomically set single key-value |
| **delete item** | `await user.preferences.adel_item("old_key")` | Atomically delete key |
| **pop** | `val = await user.preferences.apop("key")` | Atomically remove and return value |
| **pop item** | `key, val = await user.preferences.apopitem()` | Atomically remove and return arbitrary key-value pair |
| **clear** | `await user.preferences.aclear()` | Atomically clear entire dict |

Standard `dict` methods (update, clear, item assignment) work on both local copy and Redis when used with pipelines. Use async methods (apop, apopitem, etc.) for operations that require returning values.

---

## RedisBytes

**Inherits from:** `bytes`, `RedisType`  
**Redis Storage:** Base64 encoded strings (via pickle serialization)  
**Use Case:** Binary data, images, or any bytes-like data

```python
from rapyer.types import RedisBytes  # Recommended: TypeAlias
# from rapyer.types import RedisBytes     # Alternative: Direct class

class FileModel(AtomicRedisModel):
    content: RedisBytes = b""          # Flexible typing with union support
    thumbnail: RedisBytes = b""        # Accepts both bytes and RedisBytes
```

### Available Operations

| Operation | Method | Description |
|-----------|---------|-------------|
| **save** | `await file.content.asave()` | Save bytes to Redis |
| **load** | `await file.content.aload()` | Load bytes from Redis (returns value, doesn't update model) |

All standard `bytes` methods are available but operate on the local copy.

---

## RedisDatetime

**Inherits from:** `datetime`, `RedisType`  
**Redis Storage:** ISO format strings with automatic conversion  
**Use Case:** Timestamps, dates, and time-based data

```python
from rapyer.types import RedisDatetime  # Recommended: TypeAlias
# from rapyer.types import RedisDatetime     # Alternative: Direct class
from datetime import datetime

class Event(AtomicRedisModel):
    created_at: RedisDatetime = Field(default_factory=datetime.now)  # Flexible typing with union support
    updated_at: RedisDatetime                                        # Accepts both datetime and RedisDatetime
```

### Available Operations

| Operation | Method | Description |
|-----------|---------|-------------|
| **save** | `await event.created_at.asave()` | Save datetime to Redis |
| **load** | `await event.created_at.aload()` | Load datetime from Redis (returns value, doesn't update model) |

All standard `datetime` methods are available (strftime, replace, etc.) but operate on the local copy.

---

## RedisDatetimeTimestamp
A datetime field, but it will be stored in epoch time format

**Redis Storage:** Timestamp values (floats) representing seconds since Unix epoch  
**Use Case:** Timestamps requiring efficient storage or interoperability with systems expecting Unix timestamps

```python
from rapyer.types import RedisDatetimeTimestamp  # Recommended: TypeAlias
from datetime import datetime

class Event(AtomicRedisModel):
    created_at: RedisDatetimeTimestamp = Field(default_factory=datetime.now)  # Stored as timestamp
    updated_at: RedisDatetimeTimestamp                                         # Accepts datetime objects
```

### Important Notes

!!! warning "Timezone Information Loss"
    When using `RedisDatetimeTimestamp`, **timezone information is lost during storage**. The datetime is converted to a Unix timestamp (float) which represents a moment in UTC time. When loaded back, it becomes a naive datetime in the local timezone.

!!! info "Storage Format Difference"
    - **RedisDatetime**: Stores as ISO string format (e.g., "2023-01-01T12:00:00")
    - **RedisDatetimeTimestamp**: Stores as Unix timestamp float (e.g., 1672531200.0)
---

## Nested Models (BaseModel → AtomicRedisModel)

**All Pydantic BaseModel classes are automatically converted to AtomicRedisModel**, enabling atomic operations on nested structures:

```python
from pydantic import BaseModel

class Address(BaseModel):  # Automatically becomes AtomicRedisModel
    street: str
    city: str
    country: str

class Profile(BaseModel):  # Automatically becomes AtomicRedisModel  
    bio: str
    preferences: Dict[str, str] = Field(default_factory=dict)

class User(AtomicRedisModel):
    name: str
    address: Address  # Nested model with atomic operations
    profile: Profile  # Nested model with atomic operations
```

### Available Operations on Nested Models

Nested BaseModel instances support these atomic Redis operations:

| Operation | Method | Description |
|-----------|---------|-------------|
| **save** | `await user.address.asave()` | Save only this nested model to Redis (other parent fields unchanged) |
| **load** | `await user.address.aload()` | Load nested model from Redis (returns value, doesn't update model) |
| **aupdate** | `await user.address.aupdate(street="New St")` | Atomically update specific fields in the nested model |

!!! warning "Scoped Save Operation"
    When you call `await user.address.asave()`, **only the `address` nested model is saved to Redis**. Other fields in the parent `user` model remain unchanged in Redis, even if they were modified locally.

```python
# Atomic operations on nested models
await user.address.aupdate(street="123 New St", city="Boston")  # Update specific fields
await user.address.asave()  # Save entire address model only

# All fields within nested models support their respective Redis operations
await user.profile.preferences.aupdate(theme="dark", lang="en")  # Dict operations available
```

---

## Generic Type Support

For any other Python type, Rapyer provides automatic serialization via pickle:

```python
from enum import Enum
from dataclasses import dataclass

class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

@dataclass
class CustomData:
    value: str
    count: int

class MyModel(AtomicRedisModel):
    status: Status = Status.ACTIVE  # Pickled automatically
    data: CustomData  # Pickled automatically
```

!!! warning "Limited Operations"
    Custom types cannot perform atomic Redis operations like lists or dicts.

---

## Best Practices

### 1. Use Appropriate Types
- **RedisInt** for counters and numeric operations
- **RedisList** for ordered collections needing atomic operations  
- **RedisDict** for key-value data requiring atomic updates
- **Standard types** for simple data that doesn't need atomic operations

### 2. Atomic vs Local Operations
- Use `a`-prefixed methods (aappend, aupdate) for immediate Redis operations
- Use standard methods when working within pipelines or transactions
- Remember that atomic operations may not update the local instance

### 3. Performance Considerations
- Atomic operations create individual Redis commands
- Use pipelines for bulk operations
- Consider the trade-off between atomicity and performance

### 4. Legacy Note

!!! info "Legacy Direct Redis Classes"
    Direct Redis classes (`RedisDict`, `RedisList`, etc.) still work but TypeAlias types are now recommended for better MyPy compatibility and IDE support.