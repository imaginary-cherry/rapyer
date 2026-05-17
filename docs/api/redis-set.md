# RedisSet API Reference

An unordered, unique-member collection backed by a Redis **SET**. Stores data in a **separate Redis key**, not inline with the model JSON.

```python
from pydantic import Field
from rapyer.types import RedisSet

class Article(AtomicRedisModel):
    tags: RedisSet[str] = Field(default_factory=RedisSet)
```

### Inherits From
- `set` — All standard Python `set` methods available
- `SpecialFieldType` — Special field type functionality (separate Redis key storage)

## Properties

#### `special_key`
**Type:** `str`
**Description:** The Redis key for this field's set. Format: `__rapyer_special__:{model_key}:{field_name}`.

## Async Methods

#### `aadd(value)`
**Type:** `async` method
**Parameters:**
- `value` (T): The item to add
**Description:** Adds a single member to the set.

#### `aadd_many(values)`
**Type:** `async` method
**Parameters:**
- `values` (Iterable[T]): Items to add
**Description:** Adds multiple members in a single Redis command. No-op if `values` is empty.

#### `aremove(value)`
**Type:** `async` method
**Parameters:**
- `value` (T): The item to remove
**Returns:** `bool` — `True` if the item was removed, `False` if not found.
**Description:** Removes a member from the set.

#### `apop()`
**Type:** `async` method
**Description:** Atomically removes and returns a random member (Redis `SPOP`). Returns `None` if the set is empty.

#### `aclear()`
**Type:** `async` method
**Description:** Removes all members from the set.

#### `acontains(value)`
**Type:** `async` method
**Parameters:**
- `value` (T): Value to check
**Returns:** `bool`
**Description:** Checks whether `value` is a member of the set.

#### `amembers()`
**Type:** `async` method
**Returns:** `set`
**Description:** Returns all members as a native Python `set`.

#### `asize()`
**Type:** `async` method
**Returns:** `int`
**Description:** Returns the number of members.

## Set Algebra

These methods accept other `RedisSet` instances and execute on the Redis side.

#### `aunion(*others)`
**Type:** `async` method
**Parameters:**
- `*others` (RedisSet[T]): Other `RedisSet` fields
**Returns:** `set`
**Description:** Returns the union of this set with the others.

#### `aintersect(*others)`
**Type:** `async` method
**Parameters:**
- `*others` (RedisSet[T]): Other `RedisSet` fields
**Returns:** `set`
**Description:** Returns the intersection of this set with the others.

#### `adifference(*others)`
**Type:** `async` method
**Parameters:**
- `*others` (RedisSet[T]): Other `RedisSet` fields
**Returns:** `set`
**Description:** Returns members in this set that are not in any of the others.

## Sync (Pipeline) Methods

Standard Python `set` mutators. Outside a pipeline they only mutate the local set; inside a pipeline they queue the matching Redis command.

#### `add(value)`
Add a member. Queues `SADD` in a pipeline.

#### `update(*iterables)`
Add members from one or more iterables. Queues `SADD` in a pipeline.

#### `remove(value)` / `discard(value)`
Remove a member. Queues `SREM` in a pipeline. `remove` raises `KeyError` if missing; `discard` is silent.

#### `pop()`
Removes and returns a value chosen by the **local** Python set. Queues `SREM` for that value in a pipeline. Use `apop()` for an atomic Redis-side pick.

#### `clear()`
Remove all members. Queues `DELETE` of the special key.

#### `difference_update(*iterables)` / `intersection_update(*iterables)` / `symmetric_difference_update(other)`
In-place set algebra. Inside a pipeline, the special key is rewritten to match the resulting members.

#### In-Place Operators
- `|=` — calls `update`
- `&=` — calls `intersection_update`
- `-=` — calls `difference_update`
- `^=` — calls `symmetric_difference_update`

## Lifecycle Methods

#### `clone()`
**Returns:** `RedisSet`
**Description:** Returns a detached copy of the local set (no Redis binding).
