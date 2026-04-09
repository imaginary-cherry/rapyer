# RedisPriorityQueue API Reference

A priority queue field backed by a Redis Sorted Set. Stores data in a **separate Redis key**, not inline with the model JSON. Lower priority score = higher precedence.

```python
from pydantic import Field
from rapyer.types import RedisPriorityQueue

class JobQueue(AtomicRedisModel):
    tasks: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue)
```

### Inherits From
- `SpecialFieldType` - Special field type functionality (separate Redis key storage)

## Properties

#### `special_key`
**Type:** `str`  
**Description:** The Redis key for this field's sorted set. Format: `{model_key}:{field_name}`.

## Methods

#### `apush(value, priority)`
**Type:** `async` method  
**Parameters:**
- `value` (T): The item to add
- `priority` (float): Priority score (lower = popped first)  
**Description:** Adds an item to the queue with a priority score.

#### `apush_many(items)`
**Type:** `async` method  
**Parameters:**
- `items` (list[PriorityQueueItem[T]]): List of items with priorities  
**Description:** Adds multiple items in a single Redis command.

```python
from rapyer.types.priority_queue import PriorityQueueItem

await queue.tasks.apush_many([
    PriorityQueueItem(value="task_a", priority=1.0),
    PriorityQueueItem(value="task_b", priority=2.0),
])
```

#### `apop()`
**Type:** `async` method  
**Description:** Removes and returns the item with the lowest priority score. Returns `None` if the queue is empty.

#### `apeek()`
**Type:** `async` method  
**Description:** Returns the item with the lowest priority score without removing it. Returns `None` if the queue is empty.

#### `asize()`
**Type:** `async` method  
**Returns:** `int`  
**Description:** Returns the number of items in the queue.

#### `aitems()`
**Type:** `async` method  
**Returns:** `list[PriorityQueueItem]`  
**Description:** Returns all items sorted by priority (ascending).

#### `aremove(value)`
**Type:** `async` method  
**Parameters:**
- `value`: The value to remove  
**Returns:** `bool` — `True` if the item was removed, `False` if not found.

#### `aclear()`
**Type:** `async` method  
**Description:** Removes all items from the queue.

## PriorityQueueItem

Dataclass used with `apush_many()` and returned by `aitems()`.

```python
from rapyer.types.priority_queue import PriorityQueueItem

item = PriorityQueueItem(value="task", priority=1.0)
item.value     # "task"
item.priority  # 1.0
```
