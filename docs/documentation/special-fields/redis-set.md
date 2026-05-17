# Redis Set

<div style="background: linear-gradient(135deg, #7c4dff 0%, #b388ff 100%); color: white; padding: 16px 20px; border-radius: 8px; margin-bottom: 20px;">
  <strong style="font-size: 1.1em;">🧪 Beta Feature</strong><br>
  <span style="opacity: 0.95;">RedisSet is currently experimental. The API may change in future releases based on feedback.<br>Only JSON-serializable value types are supported: <code>str</code>, <code>int</code>, <code>float</code>, and <code>bool</code>.</span>
</div>

`RedisSet` is an unordered, unique-member collection backed by a Redis **SET**. Items appear only once and have no defined order.

Unlike regular Redis types (`RedisStr`, `RedisList`, etc.), `RedisSet` stores its data in a **separate Redis key** — not inline with the model's JSON. All mutations go straight to Redis.

```python
from pydantic import Field
from rapyer import AtomicRedisModel
from rapyer.types import RedisSet


class Article(AtomicRedisModel):
    title: str = "untitled"
    tags: RedisSet[str] = Field(default_factory=RedisSet)
```

Plain `set[...]` annotations are auto-converted to `RedisSet` as well:

```python
class Article(AtomicRedisModel):
    tags: set[str] = Field(default_factory=set)  # becomes RedisSet[str]
```

## Basic Usage

```python
article = Article(title="Hello Redis")
await article.asave()

await article.tags.aadd("python")
await article.tags.aadd("redis")
await article.tags.aadd("python")  # idempotent — set still has 2 members

await article.tags.acontains("python")  # True
await article.tags.asize()              # 2
await article.tags.amembers()           # {"python", "redis"}
```

## Generic Type Support

`RedisSet` accepts any JSON-serializable type as its generic parameter:

```python
class Numbers(AtomicRedisModel):
    values: RedisSet[int] = Field(default_factory=RedisSet)

class Flags(AtomicRedisModel):
    bits: RedisSet[bool] = Field(default_factory=RedisSet)
```

## Async Operations

| Operation | Method | Description |
|-----------|--------|-------------|
| **add** | `await article.tags.aadd(value)` | Add a single member |
| **add many** | `await article.tags.aadd_many(values)` | Add multiple members in one command |
| **remove** | `await article.tags.aremove(value)` | Remove a member (returns `bool`) |
| **pop** | `await article.tags.apop()` | Remove and return a random member |
| **clear** | `await article.tags.aclear()` | Remove all members |
| **contains** | `await article.tags.acontains(value)` | Check membership |
| **members** | `await article.tags.amembers()` | Return all members as a Python `set` |
| **size** | `await article.tags.asize()` | Return the number of members |

### Set Algebra Across Models

`aunion`, `aintersect`, and `adifference` operate against other `RedisSet` fields and run entirely on the Redis side:

```python
a = Article(title="A")
b = Article(title="B")
await a.asave()
await b.asave()
await a.tags.aadd_many(["alpha", "beta", "gamma"])
await b.tags.aadd_many(["gamma", "delta"])

await a.tags.aunion(b.tags)        # {"alpha", "beta", "gamma", "delta"}
await a.tags.aintersect(b.tags)    # {"gamma"}
await a.tags.adifference(b.tags)   # {"alpha", "beta"}
```

All three accept any number of other `RedisSet` operands.

## Pipeline (Sync) Operations

Inside a pipeline context, the standard Python `set` mutators are batched into atomic Redis commands:

```python
async with article.apipeline():
    article.tags.add("python")
    article.tags.update(["redis", "asyncio"])
    article.tags.discard("legacy")
    article.tags |= {"backend"}
```

Supported sync mutators:

- `add(value)`, `update(*iterables)`
- `remove(value)`, `discard(value)`, `pop()`, `clear()`
- `difference_update`, `intersection_update`, `symmetric_difference_update`
- `|=`, `&=`, `-=`, `^=`

!!! note "Sync `pop()` vs async `apop()`"
    `pop()` removes a value chosen by the **local** Python set and queues the matching `SREM` in the pipeline. `apop()` runs an atomic Redis `SPOP` and lets Redis pick the member.

## Optional Fields

`RedisSet` fields can be optional:

```python
class Worker(AtomicRedisModel):
    name: str = "default"
    tags: Optional[RedisSet[str]] = None
```

Assign a value after init to start using it:

```python
worker = Worker()
await worker.asave()

worker.tags = RedisSet()
await worker.tags.aadd("ready")
```

## How It Works

`RedisSet` is a [special field type](index.md) — it stores data in a separate Redis key derived from the parent model's key:

```
__rapyer_special__:{ModelName}:{pk}:tags
```

This means:

- **Save/delete are automatic** — `asave()` and `adelete()` on the parent model handle the set's Redis key and TTL.
- **TTL is inherited** — if the parent model has a TTL configured, the set's key gets the same expiration.
- **No inline state** — every async operation hits Redis directly.

!!! warning "Cannot use `aupdate()` with special fields"
    Special fields manage their own Redis storage and cannot be passed to `aupdate()`. Use the field's own methods instead.

    ```python
    # ❌ This raises UpdateAtomicModelError
    await article.aupdate(tags={"x"})

    # ✅ Use the field's methods directly
    await article.tags.aadd("x")
    ```
