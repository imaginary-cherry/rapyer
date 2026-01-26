# Redis Types API Reference

Rapyer provides specialized Redis-backed types that automatically sync with Redis storage. All Redis types inherit from `RedisType` and provide both synchronous and asynchronous operations.

## Common Properties

All Redis types inherit these properties from `RedisType`:

### Properties

#### `redis`
**Type:** Redis client  
**Description:** Access to the Redis client instance from the parent model.

#### `key`
**Type:** `str`  
**Description:** The Redis key of the parent model.

#### `field_path`
**Type:** `str`  
**Description:** The full path to this field within the parent model (e.g., "user.settings.theme").

#### `json_path`
**Type:** `str`  
**Description:** JSON path for Redis JSON operations (e.g., "$.user.settings.theme").

#### `client`
**Type:** Redis client  
**Description:** The Redis client or pipeline if within a pipeline context.

### Common Methods

#### `save()`
**Type:** `async` method  
**Returns:** `Self`  
**Description:** Saves the current value to Redis using JSON operations.

#### `load()`
**Type:** `async` method  
**Returns:** `Self`  
**Description:** Loads the latest value from Redis.

#### `clone()`
**Type:** Synchronous method  
**Returns:** Native Python type  
**Description:** Returns a native Python copy of the value.

---

## RedisStr

A Redis-backed string type that extends Python's built-in `str`.

```python
from rapyer.types import RedisStr

class User(AtomicRedisModel):
    name: str  # Automatically becomes RedisStr
    email: str
```

### Inherits From
- `str` - All standard string methods available
- `RedisType` - All common Redis type functionality

### Methods
All standard Python `str` methods are available (`upper()`, `lower()`, `split()`, etc.) plus:

#### In-Place String Operations (Pipeline Context)
RedisStr supports in-place string operations that automatically sync with Redis when used within a pipeline:

- `+=` - In-place concatenation
- `*=` - In-place repetition

```python
async with user.apipeline():
    user.name += " Jr."     # Append suffix
    user.prefix *= 3        # Repeat string 3 times
    # All operations applied atomically when context exits
```

#### `clone()`
**Returns:** `str`  
**Description:** Returns a native Python string copy.

```python
user = User(name="John Doe")
native_name = user.name.clone()  # Returns "John Doe" as str
```

### Example Usage

```python
class User(AtomicRedisModel):
    name: str
    email: str

user = User(name="John", email="john@example.com")
await user.asave()

# String operations work normally
print(user.name.upper())  # "JOHN"
print(user.name.startswith("J"))  # True

# Save individual field
await user.name.asave()

# Load latest value
await user.name.aload()
```

---

## RedisInt

A Redis-backed integer type that extends Python's built-in `int` with atomic increment operations.

```python
from rapyer.types import RedisInt

class Counter(AtomicRedisModel):
    count: int  # Automatically becomes RedisInt
    views: int = 0
```

### Inherits From
- `int` - All standard integer methods available
- `RedisType` - All common Redis type functionality

### Methods
All standard Python `int` methods are available plus:

#### `increase(amount=1)`
**Type:** `async` method  
**Parameters:**
- `amount` (int): Amount to increment by (default: 1)  
**Returns:** `int` - New value after increment  
**Description:** Atomically increments the value in Redis.

```python
counter = Counter(count=5)
await counter.asave()

# Atomically increment by 1
new_value = await counter.count.aincrease()  # Returns 6

# Increment by custom amount
new_value = await counter.count.aincrease(10)  # Returns 16
```

#### In-Place Arithmetic Operations (Pipeline Context)
RedisInt supports in-place arithmetic operations that automatically sync with Redis when used within a pipeline:

- `+=` - In-place addition
- `-=` - In-place subtraction
- `*=` - In-place multiplication
- `//=` - In-place floor division
- `%=` - In-place modulo
- `**=` - In-place exponentiation

```python
async with post.apipeline():
    post.views += 10    # Add 10
    post.likes *= 2     # Double likes
    post.views //= 2    # Floor division
    # All operations applied atomically when context exits
```

#### `clone()`
**Returns:** `int`
**Description:** Returns a native Python integer copy.

### Example Usage

```python
class BlogPost(AtomicRedisModel):
    title: str
    views: int = 0
    likes: int = 0

post = BlogPost(title="My Blog Post")
await post.asave()

# Atomic increment operations
await post.views.aincrease()        # Increment views by 1
await post.likes.aincrease(5)       # Increment likes by 5

# Standard integer operations
total_engagement = post.views + post.likes
is_popular = post.views > 1000
```

---

## RedisFloat

A Redis-backed float type that extends Python's built-in `float` with atomic increment operations.

```python
from rapyer.types import RedisFloat

class Product(AtomicRedisModel):
    price: float  # Automatically becomes RedisFloat
    discount: float = 0.0
```

### Inherits From
- `float` - All standard float methods available
- `RedisType` - All common Redis type functionality

### Methods
All standard Python `float` methods are available plus:

#### `aincrease(amount=1.0)`
**Type:** `async` method  
**Parameters:**
- `amount` (float): Amount to increment by (default: 1.0)  
**Returns:** `float` - New value after increment  
**Description:** Atomically increments the value in Redis.

```python
product = Product(price=99.99)
await product.asave()

# Atomically increment by 1.0
new_price = await product.price.aincrease()  # Returns 100.99

# Increment by custom amount
new_price = await product.price.aincrease(10.50)  # Returns 111.49
```

#### In-Place Arithmetic Operations (Pipeline Context)
RedisFloat supports in-place arithmetic operations that automatically sync with Redis when used within a pipeline:

- `+=` - In-place addition
- `-=` - In-place subtraction
- `*=` - In-place multiplication
- `/=` - In-place true division
- `//=` - In-place floor division
- `%=` - In-place modulo
- `**=` - In-place exponentiation

```python
async with product.apipeline():
    product.price += 10.0    # Add 10.0
    product.price *= 1.1     # Apply 10% increase
    product.discount -= 5.0  # Reduce discount by 5.0
    product.price //= 2      # Floor division
    # All operations applied atomically when context exits
```

#### `clone()`
**Returns:** `float`  
**Description:** Returns a native Python float copy.

### Example Usage

```python
class StockItem(AtomicRedisModel):
    name: str
    price: float = 0.0
    weight: float = 0.0
    rating: float = 5.0

item = StockItem(name="Widget", price=19.99, weight=2.5)
await item.asave()

# Atomic increment operations
await item.price.aincrease(5.0)      # Increase price by 5.0
await item.rating.aincrease(-0.5)    # Decrease rating by 0.5

# Standard float operations
average_value = item.price / item.weight
is_expensive = item.price > 100.0

# Batch operations in pipeline
async with item.apipeline():
    item.price *= 0.9      # 10% discount
    item.weight += 0.1     # Adjust weight
```

---

## RedisList

A Redis-backed list type that extends Python's built-in `list` with atomic operations.

```python
from rapyer.types import RedisList
from typing import List

class User(AtomicRedisModel):
    tags: List[str]  # Automatically becomes RedisList[str]
    scores: List[int] = []
```

### Inherits From
- `list` - All standard list methods available
- `GenericRedisType` - Generic Redis type functionality

### Synchronous Methods (Work in Pipeline Context)
These methods work immediately in pipeline contexts and batch operations:

#### `append(item)`
**Parameters:**
- `item`: Item to append  
**Description:** Adds item to end of list. In pipeline context, operation is batched.

#### `extend(iterable)`
**Parameters:**
- `iterable`: Items to append  
**Description:** Extends list with items. In pipeline context, operation is batched.

#### `insert(index, item)`
**Parameters:**
- `index` (int): Position to insert
- `item`: Item to insert  
**Description:** Inserts item at specified index. In pipeline context, operation is batched.

#### `clear()`
**Description:** Removes all items from list. In pipeline context, operation is batched.

#### `remove_range(start, end)`
**Parameters:**
- `start` (int): Start index (inclusive). Supports negative indices.
- `end` (int): End index (exclusive). Supports negative indices.
**Description:** Removes items from index `start` to `end` (exclusive), similar to `del list[start:end]`. 
This function has effect only within a pipeline context - when called outside a pipeline, no changes are made to either the local list or Redis. Uses an atomic Lua script to avoid race conditions.

**Index Handling:**
- Negative indices count from the end (e.g., `-1` is the last element)
- If `end` exceeds list length, it is trimmed to the list length
- If `start` exceeds list length, no operation is performed

```python
playlist = Playlist(name="My Songs", songs=["a", "b", "c", "d", "e"])
await playlist.asave()

async with playlist.apipeline():
    playlist.songs.remove_range(1, 3)  # Removes "b" and "c"
    # Result: ["a", "d", "e"]

# Negative indices
async with playlist.apipeline():
    playlist.songs.remove_range(-2, -1)  # Removes second-to-last item
```

#### `__setitem__(index, value)`
**Parameters:**
- `index` (int): Index to set
- `value`: New value  
**Description:** Sets item at index. In pipeline context, operation is batched.

#### `__iadd__(other)`
**Parameters:**
- `other`: List to append  
**Returns:** `Self`  
**Description:** Implements `+=` operator. In pipeline context, operation is batched.

```python
user = User(tags=["python"])
await user.asave()

# Use in pipeline for atomic batch operations
async with user.apipeline():
    user.tags.append("redis")
    user.tags.extend(["asyncio", "web"])
    user.tags += ["backend"]  # Uses __iadd__
    # All operations applied atomically when context exits
```

### Asynchronous Methods (Immediate Redis Operations)
These methods immediately update Redis:

#### `aappend(item)`
**Type:** `async` method  
**Parameters:**
- `item`: Item to append  
**Description:** Immediately appends item to Redis list.

#### `aextend(iterable)`
**Type:** `async` method  
**Parameters:**
- `iterable`: Items to append  
**Description:** Immediately extends Redis list with items.

#### `ainsert(index, item)`
**Type:** `async` method  
**Parameters:**
- `index` (int): Position to insert
- `item`: Item to insert  
**Description:** Immediately inserts item at index in Redis list.

#### `aclear()`
**Type:** `async` method  
**Description:** Immediately clears Redis list.

#### `apop(index=-1)`
**Type:** `async` method  
**Parameters:**
- `index` (int): Index to pop (default: -1 for last item)  
**Returns:** Popped item or `None` if list is empty  
**Description:** Atomically pops and returns item from Redis list.

#### `clone()`
**Returns:** `list`  
**Description:** Returns a native Python list copy with cloned Redis type elements.

### Example Usage

```python
class Playlist(AtomicRedisModel):
    name: str
    songs: List[str] = []
    ratings: List[int] = []

playlist = Playlist(name="My Favorites", songs=["Song 1"])
await playlist.asave()

# Immediate Redis operations
await playlist.songs.aappend("Song 2")
await playlist.songs.aextend(["Song 3", "Song 4"])
await playlist.songs.ainsert(1, "Song 1.5")

# Pop operations
last_song = await playlist.songs.apop()      # Returns "Song 4"
first_song = await playlist.songs.apop(0)    # Returns "Song 1"

# Batch operations in pipeline
async with playlist.apipeline():
    playlist.songs.append("New Song")
    playlist.ratings.extend([5, 4, 5])
    playlist.songs.clear()  # Will be executed last, atomically
```

---

## RedisDict

A Redis-backed dictionary type that extends Python's built-in `dict` with atomic operations.

```python
from rapyer.types import RedisDict
from typing import Dict

class User(AtomicRedisModel):
    settings: Dict[str, str]  # Automatically becomes RedisDict[str, str]
    metadata: Dict[str, int] = {}
```

### Inherits From
- `dict` - All standard dictionary methods available
- `GenericRedisType` - Generic Redis type functionality

### Synchronous Methods (Work in Pipeline Context)

#### `update(m=None, **kwargs)`
**Parameters:**
- `m` (dict): Dictionary to merge
- `**kwargs`: Key-value pairs to update  
**Description:** Updates dictionary. In pipeline context, operation is batched.

#### `clear()`
**Description:** Removes all items from dictionary. In pipeline context, operation is batched.

#### `__setitem__(key, value)`
**Parameters:**
- `key`: Dictionary key
- `value`: Value to set  
**Description:** Sets dictionary item. In pipeline context, operation is batched.

```python
user = User(settings={"theme": "light"})
await user.asave()

# Use in pipeline for atomic batch operations
async with user.apipeline():
    user.settings.update({"theme": "dark", "lang": "en"})
    user.settings["notifications"] = "enabled"
    user.metadata.clear()
    # All operations applied atomically when context exits
```

### Asynchronous Methods (Immediate Redis Operations)

#### `aset_item(key, value)`
**Type:** `async` method  
**Parameters:**
- `key`: Dictionary key
- `value`: Value to set  
**Description:** Immediately sets dictionary item in Redis.

#### `adel_item(key)`
**Type:** `async` method  
**Parameters:**
- `key`: Dictionary key to delete  
**Description:** Immediately deletes dictionary item from Redis.

#### `aupdate(**kwargs)`
**Type:** `async` method  
**Parameters:**
- `**kwargs`: Key-value pairs to update  
**Description:** Immediately updates dictionary in Redis.

#### `apop(key, default=None)`
**Type:** `async` method  
**Parameters:**
- `key`: Dictionary key to pop
- `default`: Default value if key doesn't exist  
**Returns:** Popped value or default  
**Description:** Atomically pops and returns dictionary item from Redis.

#### `apopitem()`
**Type:** `async` method  
**Returns:** `(key, value)` tuple  
**Raises:** `KeyError` if dictionary is empty  
**Description:** Atomically pops and returns an arbitrary dictionary item from Redis.

#### `aclear()`
**Type:** `async` method  
**Description:** Immediately clears Redis dictionary.

#### `clone()`
**Returns:** `dict`  
**Description:** Returns a native Python dictionary copy with cloned Redis type elements.

### Example Usage

```python
class UserProfile(AtomicRedisModel):
    username: str
    settings: Dict[str, str] = {}
    scores: Dict[str, int] = {}

user = UserProfile(username="john", settings={"theme": "light"})
await user.asave()

# Immediate Redis operations
await user.settings.aset_item("language", "en")
await user.settings.aupdate(theme="dark", notifications="on")

# Pop operations
theme = await user.settings.apop("theme")         # Returns "dark"
setting = await user.settings.apopitem()         # Returns ("language", "en")

# Delete operations
await user.settings.adel_item("notifications")

# Batch operations in pipeline
async with user.apipeline():
    user.settings.update({"theme": "blue", "font": "large"})
    user.scores["game1"] = 100
    user.scores["game2"] = 85
```

---

## RedisBytes

A Redis-backed bytes type that extends Python's built-in `bytes` with automatic serialization.

```python
from rapyer.types import RedisBytes

class Document(AtomicRedisModel):
    content: bytes  # Automatically becomes RedisBytes
    thumbnail: bytes = b""
```

### Inherits From
- `bytes` - All standard bytes methods available
- `RedisType` - All common Redis type functionality

### Special Features

#### Automatic Serialization
RedisBytes automatically handles serialization/deserialization when saving to/loading from Redis using base64 encoding.

#### `clone()`
**Returns:** `bytes`  
**Description:** Returns a native Python bytes copy.

### Example Usage

```python
class Image(AtomicRedisModel):
    name: str
    data: bytes
    metadata: bytes = b""

# Binary data is automatically handled
with open("image.png", "rb") as f:
    image_data = f.read()

image = Image(name="profile.png", data=image_data)
await image.asave()  # Automatically serializes bytes data

# Load and work with bytes
await image.aload()
print(len(image.data))  # Works like normal bytes
```

---

## RedisDatetime

A Redis-backed datetime type that extends Python's `datetime.datetime`.

```python
from rapyer.types import RedisDatetime
from datetime import datetime

class Event(AtomicRedisModel):
    name: str
    created_at: datetime  # Automatically becomes RedisDatetime
    updated_at: datetime = None
```

### Inherits From
- `datetime.datetime` - All standard datetime methods available
- `RedisType` - All common Redis type functionality

### Special Features

#### Enhanced Constructor
Supports initialization from existing datetime objects while preserving timezone information and microseconds.

#### `clone()`
**Returns:** `datetime`  
**Description:** Returns a native Python datetime copy.

### Example Usage

```python
from datetime import datetime, timezone

class BlogPost(AtomicRedisModel):
    title: str
    created_at: datetime
    published_at: datetime = None

# Create with current time
post = BlogPost(
    title="My Post", 
    created_at=datetime.now(timezone.utc)
)
await post.asave()

# Datetime operations work normally
age = datetime.now(timezone.utc) - post.created_at
is_recent = age.days < 7

# Update timestamp
post.published_at = datetime.now(timezone.utc)
await post.asave()
```

---

## RedisDatetimeTimestamp

A Redis-backed datetime type that stores values as Unix timestamps (floats) instead of ISO strings.

```python
from rapyer.types import RedisDatetimeTimestamp
from datetime import datetime

class Event(AtomicRedisModel):
    name: str
    created_at: RedisDatetimeTimestamp  # Stored as timestamp float
    updated_at: RedisDatetimeTimestamp = None
```

### Special Features

#### Timestamp Storage Format
Stores datetime values as Unix timestamps (float) in Redis instead of ISO strings, providing:
- **Efficient storage**: Floats are more compact than ISO strings
- **External compatibility**: Unix timestamps are widely supported
- **Numeric operations**: Direct timestamp calculations possible

!!! warning "Timezone Information Loss"
    **Timezone information is lost** when storing as timestamps. Values are converted to Unix timestamps (UTC moments) and restored as naive datetimes in local timezone.

#### Storage Comparison
- **RedisDatetime**: `"2023-01-01T12:00:00"` (ISO string)
- **RedisDatetimeTimestamp**: `1672531200.0` (Unix timestamp float)

### Example Usage

```python
from datetime import datetime, timezone

class Analytics(AtomicRedisModel):
    event_name: str
    timestamp: RedisDatetimeTimestamp  # Efficient timestamp storage
    session_start: RedisDatetimeTimestamp
    session_end: RedisDatetimeTimestamp = None

# Create with current time
analytics = Analytics(
    event_name="user_login",
    timestamp=datetime.now(),
    session_start=datetime.now(timezone.utc)  # Timezone will be lost
)
await analytics.asave()

# Datetime operations work normally
duration = analytics.session_end - analytics.session_start if analytics.session_end else None

# Efficient timestamp-based queries and storage
epoch_time = analytics.timestamp.timestamp()
```
---

## Type Conversion

When you define model fields with standard Python types, they are automatically converted to their Redis-backed equivalents:

```python
class Example(AtomicRedisModel):
    text: str                    # → RedisStr
    number: int                  # → RedisInt
    decimal: float               # → RedisFloat
    data: bytes                  # → RedisBytes
    timestamp: datetime          # → RedisDatetime (ISO string storage)
    epoch_time: RedisDatetimeTimestamp  # → RedisDatetimeTimestamp (timestamp storage)
    tags: List[str]             # → RedisList[str]
    settings: Dict[str, str]    # → RedisDict[str, str]
    scores: List[int]           # → RedisList[int]
    metadata: Dict[str, Any]    # → RedisDict[str, Any]
```

!!! note "Datetime Type Choice"
    Use `RedisDatetimeTimestamp` explicitly when you need timestamp storage format. Regular `datetime` annotation automatically becomes `RedisDatetime` with ISO string storage.

## Pipeline Context

All Redis types support pipeline operations for atomic batch execution:

```python
async with model.apipeline():
    model.tags.append("new-tag")  # Batched
    model.settings["key"] = "value"  # Batched
    model.counter += 1  # Batched
    # All operations execute atomically when context exits
```

## Error Handling

Redis type operations may raise:

- **`KeyNotFound`**: When trying to load a field that doesn't exist
- **`ConnectionError`**: When Redis is unavailable
- **`ValueError`**: When invalid data types are provided
- **`KeyError`**: When dictionary operations fail (e.g., `popitem()` on empty dict)

```python
from rapyer.errors import KeyNotFound

try:
    await redis_list.aload()
except KeyNotFound:
    print("Field not found in Redis")
```