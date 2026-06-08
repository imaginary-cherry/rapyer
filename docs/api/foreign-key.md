# Reference API Reference

`Reference[T]` declares a typed, lazy reference to another `AtomicRedisModel`. Stored inline in the parent's JSON as the target's Redis key string; the target is fetched on demand.

```python
from rapyer.types import Reference

class Book(AtomicRedisModel):
    author: Reference[Author]
```

## Accepted Values

A reference field accepts any of the following, normalizing them to a reference:

- an `AtomicRedisModel` instance (the target itself)
- a key string (the target's Redis key, e.g. `"Author:abc-123"`)
- another reference
- a `{"$ref": ..., "$id": ...}` dict

## Properties

#### `target_key`
**Type:** `str | None`
**Description:** The referenced model's Redis key, or `None` if unset.

#### `is_resolved`
**Type:** `bool`
**Description:** Whether the target has been hydrated into memory.

#### `value`
**Type:** `AtomicRedisModel`
**Description:** The hydrated target instance. Prefer reading the target's fields directly on the reference (`book.author.name`); `value` is for when you need the target model object itself. Raises `NotResolvedError` if accessed before `afetch()`.

## Async Methods

#### `afetch()`
**Type:** `async` method
**Description:** Resolves the target from Redis and caches it in place. Idempotent — returns the cached instance on subsequent calls. Raises `KeyNotFound` if the target key does not exist, or `NotResolvedError` if there is no target key to fetch.

#### `aunload()`
**Type:** `async` method
**Description:** Drops the hydrated target instance while preserving `target_key`.

## Attribute Delegation

Once resolved, field access on the reference delegates to the target:

```python
await book.author.afetch()
book.author.name        # delegates to the target instance
```

Accessing any non-private attribute before resolution raises `NotResolvedError` — attribute access never triggers I/O.
