# Priority Queue

<div style="background: linear-gradient(135deg, #7c4dff 0%, #b388ff 100%); color: white; padding: 16px 20px; border-radius: 8px; margin-bottom: 20px;">
  <strong style="font-size: 1.1em;">🧪 Beta Feature</strong><br>
  <span style="opacity: 0.95;">RedisPriorityQueue is currently experimental. The API may change in future releases based on feedback.<br>Only JSON-serializable value types are supported: <code>str</code>, <code>int</code>, <code>float</code>, and <code>bool</code>.</span>
</div>

`RedisPriorityQueue` is a priority queue field backed by a Redis Sorted Set. Items with **lower priority scores are popped first**.

Unlike regular Redis types (`RedisStr`, `RedisList`, etc.), the priority queue stores its data in a **separate Redis key** — not inline with the model's JSON. This means it operates as a pure Redis proxy with no local state.

!!! warning "Always declare priority queue fields with `exclude=True`"
    A priority queue isn't a real field on your model — its data lives only on the
    server (Redis), never inside the model itself. So you must mark it with
    `Field(..., exclude=True)`. Without it, dumping the model (e.g.
    `model_dump(mode="json")`) will raise an error.

```python
from pydantic import Field
from rapyer import AtomicRedisModel
from rapyer.types import RedisPriorityQueue


class JobQueue(AtomicRedisModel):
    name: str = "default"
    tasks: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue, exclude=True)
```

## Basic Usage

```python
queue = JobQueue(name="emails")
await queue.asave()

# Push items with a priority score
await queue.tasks.apush("send_welcome", priority=1.0)
await queue.tasks.apush("send_digest", priority=3.0)
await queue.tasks.apush("send_alert", priority=2.0)

# Pop returns the item with the lowest score
task = await queue.tasks.apop()  # "send_welcome"
task = await queue.tasks.apop()  # "send_alert"
task = await queue.tasks.apop()  # "send_digest"
task = await queue.tasks.apop()  # None (empty)
```

## Generic Type Support

`RedisPriorityQueue` accepts any JSON-serializable type as its generic parameter:

```python
class IntQueue(AtomicRedisModel):
    scores: RedisPriorityQueue[int] = Field(default_factory=RedisPriorityQueue, exclude=True)

class FloatQueue(AtomicRedisModel):
    measurements: RedisPriorityQueue[float] = Field(
        default_factory=RedisPriorityQueue, exclude=True
    )
```

## Operations

| Operation | Method | Description |
|-----------|--------|-------------|
| **push** | `await queue.tasks.apush(value, priority)` | Add an item with a priority score |
| **push many** | `await queue.tasks.apush_many(items)` | Add multiple items at once |
| **pop** | `await queue.tasks.apop()` | Remove and return the lowest-priority item |
| **peek** | `await queue.tasks.apeek()` | Return the lowest-priority item without removing it |
| **size** | `await queue.tasks.asize()` | Return the number of items |
| **items** | `await queue.tasks.aitems()` | Return all items sorted by priority |
| **remove** | `await queue.tasks.aremove(value)` | Remove a specific value |
| **clear** | `await queue.tasks.aclear()` | Remove all items |

### Batch Push

Use `PriorityQueueItem` to push multiple items in a single Redis command:

```python
from rapyer.types.priority_queue import PriorityQueueItem

await queue.tasks.apush_many([
    PriorityQueueItem(value="task_a", priority=1.0),
    PriorityQueueItem(value="task_b", priority=2.0),
    PriorityQueueItem(value="task_c", priority=3.0),
])
```

### Listing Items

`aitems()` returns a list of `PriorityQueueItem` objects sorted by priority (ascending):

```python
items = await queue.tasks.aitems()
for item in items:
    print(f"{item.value} (priority: {item.priority})")
```

## Optional Fields

Priority queue fields can be optional:

```python
class Worker(AtomicRedisModel):
    name: str = "default"
    tasks: Optional[RedisPriorityQueue[str]] = None
```

Set the field after initialization to start using it:

```python
worker = Worker()
await worker.asave()

worker.tasks = RedisPriorityQueue()
await worker.tasks.apush("job_1", priority=1.0)
```

## How It Works

`RedisPriorityQueue` is a **special field type** — it stores data in a separate Redis key derived from the parent model's key:

```
__rapyer_special__:{ModelName}:{pk}:tasks
```

This means:

- **Save/delete are automatic** — calling `asave()` or `adelete()` on the parent model handles the priority queue's Redis key and TTL automatically.
- **TTL is inherited** — if the parent model has a TTL configured, the queue's key gets the same expiration.
- **No local state** — all operations (`apush`, `apop`, etc.) go directly to Redis.

!!! warning "Cannot use `aupdate()` with special fields"
    Special fields manage their own Redis storage and cannot be passed to `aupdate()`. Use the field's own methods instead.

    ```python
    # ❌ This raises UpdateAtomicModelError
    await model.aupdate(tasks=some_value)

    # ✅ Use the field's methods directly
    await model.tasks.apush("value", priority=1.0)
    ```
