# Foreign Keys

<div style="background: linear-gradient(135deg, #7c4dff 0%, #b388ff 100%); color: white; padding: 16px 20px; border-radius: 8px; margin-bottom: 20px;">
  <strong style="font-size: 1.1em;">🧪 Beta Feature</strong><br>
  <span style="opacity: 0.95;">Foreign keys are currently experimental. TTL cascade is available today — see <a href="ttl-cascade.md" style="color: white; text-decoration: underline;">TTL Cascade</a>. Save/delete cascade and eager loading with depth control remain follow-up work. The API may change based on feedback.</span>
</div>

`Reference[T]` is a typed, lazy reference from one model to another. Instead of embedding the target document, the parent stores just the target's Redis key string (e.g. `"Author:abc-123"`) inline in its own JSON. The referenced model is fetched on demand.

For readers who want cascade-specific behavior — propagating a TTL refresh across
references — see [TTL Cascade](ttl-cascade.md).

```python
from rapyer import AtomicRedisModel
from rapyer.types import Reference


class Author(AtomicRedisModel):
    name: str = "anon"


class Book(AtomicRedisModel):
    title: str = "untitled"
    author: Reference[Author]
```

## Assigning a Reference

A reference field accepts several forms. Most often you assign a model instance directly:

```python
alice = Author(name="alice")
await alice.asave()

book = Book(title="Redis in Action", author=alice)
await book.asave()
```

You can also assign a raw key string, another reference, or a `{"$ref": ..., "$id": ...}` reference dict:

```python
book = Book(title="x", author="Author:abc-123")
book = Book(title="x", author={"$ref": "Author", "$id": "abc-123"})
```

!!! note "Existence is not validated on save"
    Saving a model does **not** check that the referenced key actually exists in Redis. A reference is stored as a plain key string, so you can save a `Book` pointing at an `Author` that has never been created (or has since been deleted). The missing target only surfaces later, when you call `afetch()` and get a `KeyNotFound`. Referential-integrity enforcement may land in a follow-up release.

## Lazy Resolution

When you load a model, its references come back **unresolved** — the key is known, but the target is not yet fetched:

```python
loaded = await Book.aget(book.key)

loaded.author.is_resolved   # False
loaded.author.target_key    # "Author:abc-123"
```

Call `afetch()` to load the target from Redis and cache it in place. Once resolved, read the target's fields directly on the reference:

```python
await loaded.author.afetch()

loaded.author.is_resolved   # True
loaded.author.name          # "alice"  — read fields straight off the reference
```

`afetch()` is idempotent — a second call returns the cached instance without hitting Redis.

Accessing a field before resolution raises `NotResolvedError` rather than triggering hidden I/O — attribute access cannot await, so resolution is always explicit:

```python
loaded.author.name          # ❌ raises NotResolvedError — call afetch() first
```

### Releasing a Target

Drop the hydrated instance while keeping the key reference:

```python
await loaded.author.aunload()

loaded.author.is_resolved   # False
loaded.author.target_key    # "Author:abc-123"  — preserved
```

## Optional and List Fields

References work as optional fields and inside lists:

```python
from typing import Optional


class Book(AtomicRedisModel):
    title: str = "untitled"
    author: Reference[Author]
    publisher: Optional[Reference[Publisher]] = None
    co_authors: list[Reference[Author]] = []
```

Each reference in a list resolves independently — fetching one does not fetch the others:

```python
loaded = await Book.aget(book.key)

await loaded.co_authors[0].afetch()
loaded.co_authors[0].is_resolved   # True
loaded.co_authors[1].is_resolved   # False
```

## Self-References and Forward Refs

Use a string parameter to reference a model that isn't defined yet, including the model itself:

```python
class Tree(AtomicRedisModel):
    name: str = "root"
    parent: Optional[Reference["Tree"]] = None
```

The name is resolved against the registered rapyer models at initialization time (by `resolve_relational_targets`); `afetch()` then uses that cached target class to load by key:

```python
child = await Tree.aget(child.key)
await child.parent.afetch()
child.parent.name           # "root"
```

## Missing Targets

If the referenced key no longer exists in Redis, `afetch()` raises `KeyNotFound`:

```python
book = Book(title="x", author="Author:deleted")
await book.asave()
loaded = await Book.aget(book.key)

await loaded.author.afetch()   # ❌ raises KeyNotFound
```

## How It Works

Unlike [special fields](index.md), which store data under a separate Redis key, a reference is stored **inline** in the parent's JSON as the target's key string. The target model lives at its own top-level key and is fetched independently — so its nested and special fields read from their own paths, not through the parent.
