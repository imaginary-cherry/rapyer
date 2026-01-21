# Foreign Key Support Design Document

## Overview

This document outlines the design for adding foreign key support to rapyer, inspired by Beanie ODM's relationship system but optimized for Redis's single-threaded, key-value architecture.

## Goals

1. **Single Link**: Support a field that references another model by key
2. **List of Links**: Support a list of references to other models
3. **Extract with Foreign Keys**: Fetch linked models in a **single Redis round-trip**
4. **Delete Cascade**: Delete linked models atomically in a **single Redis round-trip**
5. **Configurable**: Fine-grained control over which links to fetch/cascade

## Design Principles

- **Single Trip**: All multi-key operations use Lua scripts for atomicity
- **Explicit over Implicit**: Users must explicitly request link fetching/cascade
- **Type Safety**: Full Pydantic v2 type validation
- **Backward Compatible**: Existing models work unchanged

---

## 1. Link Types

### 1.1 Link[Model] - Single Reference

```python
from rapyer import AtomicRedisModel, Link

class Author(AtomicRedisModel):
    name: str

class Book(AtomicRedisModel):
    title: str
    author: Link[Author]  # Stores "Author:uuid" as string
```

**Storage Format:**
```json
{
  "title": "The Great Gatsby",
  "author": "Author:550e8400-e29b-41d4-a716-446655440000"
}
```

### 1.2 list[Link[Model]] - List of References

```python
class Tag(AtomicRedisModel):
    name: str

class Article(AtomicRedisModel):
    title: str
    tags: list[Link[Tag]]  # Stores ["Tag:uuid1", "Tag:uuid2"]
```

**Storage Format:**
```json
{
  "title": "Python Tips",
  "tags": ["Tag:abc123", "Tag:def456", "Tag:ghi789"]
}
```

### 1.3 Optional Links

```python
class Post(AtomicRedisModel):
    title: str
    author: Link[Author] | None = None  # Optional single link
    related: list[Link[Post]] = []       # Optional list (empty default)
```

---

## 2. Link Class Implementation

```python
from typing import Generic, TypeVar, TYPE_CHECKING
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

M = TypeVar("M", bound="AtomicRedisModel")

class Link(Generic[M]):
    """
    A foreign key reference to another AtomicRedisModel.

    When not fetched: stores the key string (e.g., "Author:uuid")
    When fetched: stores the actual model instance
    """

    __slots__ = ("_key", "_model", "_model_class", "_is_fetched")

    def __init__(
        self,
        ref: str | M,
        model_class: type[M] | None = None
    ):
        if isinstance(ref, str):
            self._key = ref
            self._model = None
            self._is_fetched = False
        else:
            # ref is a model instance
            self._key = ref.key
            self._model = ref
            self._is_fetched = True

        self._model_class = model_class

    @property
    def key(self) -> str:
        """The Redis key of the linked model."""
        return self._key

    @property
    def pk(self) -> str:
        """The primary key (ID portion) of the linked model."""
        # Extract pk from key like "Author:uuid" -> "uuid"
        return self._key.split(":", 1)[1] if ":" in self._key else self._key

    @property
    def is_fetched(self) -> bool:
        """Whether the linked model has been fetched."""
        return self._is_fetched

    @property
    def model(self) -> M | None:
        """
        The fetched model instance, or None if not fetched.
        Use await link.afetch() to fetch it.
        """
        return self._model

    def __repr__(self) -> str:
        if self._is_fetched:
            return f"Link({self._model!r})"
        return f"Link('{self._key}')"

    async def afetch(self) -> M:
        """Fetch the linked model from Redis."""
        if not self._is_fetched:
            self._model = await self._model_class.aget(self._key)
            self._is_fetched = True
        return self._model

    # Pydantic integration
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        # Extract the model type from Link[Model]
        from typing import get_args
        args = get_args(source_type)
        model_class = args[0] if args else None

        def validate_link(value) -> Link:
            if isinstance(value, Link):
                return value
            if isinstance(value, str):
                # Key string from Redis
                return Link(value, model_class=model_class)
            if hasattr(value, "key"):
                # Model instance
                return Link(value, model_class=model_class)
            raise ValueError(f"Cannot create Link from {type(value)}")

        def serialize_link(link: Link, info) -> str:
            # Always serialize to key string for Redis storage
            return link.key

        return core_schema.with_info_plain_validator_function(
            lambda v, info: validate_link(v),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_link,
                info_arg=True,
                return_schema=core_schema.str_schema(),
            ),
        )
```

---

## 3. Extraction (Fetching Linked Models)

### 3.1 API Design

```python
# Fetch a single model with all its links populated
book = await Book.aget("Book:123", fetch_links=True)
print(book.author.model.name)  # "F. Scott Fitzgerald"

# Fetch with selective links
book = await Book.aget("Book:123", fetch_links=["author"])

# Fetch with nesting depth (for self-referential or deep links)
article = await Article.aget("Article:123", fetch_links=True, nesting_depth=2)

# Bulk fetch with links
books = await Book.afind(fetch_links=True)

# Instance method to fetch links after initial load
book = await Book.aget("Book:123")  # Links not fetched
await book.afetch_links()           # Now fetch all links
await book.afetch_links(["author"]) # Or fetch specific links
```

### 3.2 Configurable Fetch Options

```python
from rapyer import FetchConfig

# Model-level default configuration
class Book(AtomicRedisModel):
    title: str
    author: Link[Author]
    publisher: Link[Publisher]

    class Settings:
        # Default links to fetch (can be overridden per-query)
        default_fetch_links = ["author"]  # Only fetch author by default

# Query-level override
book = await Book.aget(
    "Book:123",
    fetch_links=FetchConfig(
        include=["author", "publisher"],  # Fetch these
        exclude=[],                        # Or exclude these
        nesting_depth=1,                   # How deep to go
    )
)
```

### 3.3 Lua Script for Atomic Fetch

The key insight: we need to fetch the main model AND all linked models in a single round-trip.

```lua
-- FETCH_WITH_LINKS_SCRIPT
-- KEYS[1] = main model key
-- ARGV[1] = JSON-encoded list of link field paths
-- ARGV[2] = nesting depth
-- Returns: JSON object with main model and all linked models

local main_key = KEYS[1]
local link_paths = cjson.decode(ARGV[1])
local max_depth = tonumber(ARGV[2]) or 1

-- Get the main model
local main_data = redis.call('JSON.GET', main_key)
if not main_data or main_data == 'null' then
    return nil
end

local main_obj = cjson.decode(main_data)
local result = {
    __main__ = main_obj,
    __links__ = {}
}

-- Collect all link keys to fetch
local keys_to_fetch = {}

for _, path in ipairs(link_paths) do
    -- Navigate to the field value using the path
    local value = main_obj
    for part in string.gmatch(path, "[^.]+") do
        if value and type(value) == "table" then
            value = value[part]
        else
            value = nil
            break
        end
    end

    if value then
        if type(value) == "string" then
            -- Single link
            keys_to_fetch[value] = path
        elseif type(value) == "table" then
            -- List of links
            for i, key in ipairs(value) do
                keys_to_fetch[key] = path .. "[" .. (i-1) .. "]"
            end
        end
    end
end

-- Fetch all linked models in batch
for key, path in pairs(keys_to_fetch) do
    local linked_data = redis.call('JSON.GET', key)
    if linked_data and linked_data ~= 'null' then
        result.__links__[key] = cjson.decode(linked_data)
    end
end

return cjson.encode(result)
```

### 3.4 Alternative: Pipeline-Based Approach

For simpler cases without deep nesting, we can use Redis pipelines:

```python
async def _fetch_with_links(
    cls,
    key: str,
    link_fields: list[str] | None = None
) -> Self:
    """Fetch model with links using pipeline."""

    async with cls.Meta.redis.pipeline(transaction=False) as pipe:
        # Queue main model fetch
        pipe.json().get(key)

        # We need to first get the main model to know which links to fetch
        # This requires a two-phase approach for pipeline
        pass

    # Better: Use Lua script for true single-trip
```

---

## 4. Deletion with Cascade

### 4.1 Delete Rules Enum

```python
from enum import Enum

class DeleteRules(str, Enum):
    """Rules for handling linked models during deletion."""

    DO_NOTHING = "do_nothing"
    """Keep linked models (default)."""

    CASCADE = "cascade"
    """Delete all linked models recursively."""

    SET_NULL = "set_null"
    """Set the link field to null in referring models (back-reference)."""
```

### 4.2 API Design

```python
# Delete just the book (default behavior)
await book.adelete()

# Delete book and cascade to linked models
await book.adelete(link_rule=DeleteRules.CASCADE)

# Delete with selective cascade
await book.adelete(
    link_rule=DeleteRules.CASCADE,
    cascade_links=["draft_versions"]  # Only cascade these links
)

# Bulk delete with cascade
await Book.adelete_many(["Book:1", "Book:2"], link_rule=DeleteRules.CASCADE)
```

### 4.3 Lua Script for Atomic Cascade Delete

```lua
-- CASCADE_DELETE_SCRIPT
-- KEYS[1] = main model key
-- ARGV[1] = JSON-encoded list of link field paths to cascade
-- ARGV[2] = max recursion depth
-- Returns: number of deleted keys

local main_key = KEYS[1]
local cascade_paths = cjson.decode(ARGV[1])
local max_depth = tonumber(ARGV[2]) or 10
local deleted_count = 0
local visited = {}

local function collect_keys_to_delete(key, depth)
    if depth > max_depth or visited[key] then
        return {}
    end
    visited[key] = true

    local keys = {key}
    local data = redis.call('JSON.GET', key)

    if not data or data == 'null' then
        return keys
    end

    local obj = cjson.decode(data)

    -- Extract link keys from specified paths
    for _, path in ipairs(cascade_paths) do
        local value = obj
        for part in string.gmatch(path, "[^.]+") do
            if value and type(value) == "table" then
                value = value[part]
            else
                value = nil
                break
            end
        end

        if value then
            if type(value) == "string" then
                -- Single link
                local sub_keys = collect_keys_to_delete(value, depth + 1)
                for _, k in ipairs(sub_keys) do
                    table.insert(keys, k)
                end
            elseif type(value) == "table" then
                -- List of links
                for _, linked_key in ipairs(value) do
                    local sub_keys = collect_keys_to_delete(linked_key, depth + 1)
                    for _, k in ipairs(sub_keys) do
                        table.insert(keys, k)
                    end
                end
            end
        end
    end

    return keys
end

-- Collect all keys to delete
local all_keys = collect_keys_to_delete(main_key, 0)

-- Delete all collected keys atomically
for _, key in ipairs(all_keys) do
    redis.call('DEL', key)
    deleted_count = deleted_count + 1
end

return deleted_count
```

---

## 5. Link Field Configuration

### 5.1 Field-Level Configuration

```python
from rapyer import Link, LinkConfig

class Book(AtomicRedisModel):
    title: str

    # Simple link
    author: Link[Author]

    # Link with configuration
    publisher: Annotated[
        Link[Publisher],
        LinkConfig(
            on_delete=DeleteRules.DO_NOTHING,  # Don't cascade delete
            fetch_by_default=False,             # Don't auto-fetch
        )
    ]

    # Link that should cascade delete
    draft: Annotated[
        Link[Draft] | None,
        LinkConfig(
            on_delete=DeleteRules.CASCADE,     # Delete draft when book deleted
            fetch_by_default=True,              # Always fetch with book
        )
    ] = None
```

### 5.2 LinkConfig Dataclass

```python
from dataclasses import dataclass

@dataclass
class LinkConfig:
    """Configuration for a Link field."""

    on_delete: DeleteRules = DeleteRules.DO_NOTHING
    """What to do with linked model when this model is deleted."""

    fetch_by_default: bool = False
    """Whether to fetch this link by default in aget/afind."""

    back_populates: str | None = None
    """Field name in linked model that refers back to this model."""
```

---

## 6. Implementation Architecture

### 6.1 New Files Structure

```
rapyer/
├── fields/
│   ├── link.py          # Link class and LinkConfig
│   └── ...
├── types/
│   └── ...
├── enums.py             # DeleteRules, WriteRules enums
├── scripts.py           # Add FETCH_LINKS and CASCADE_DELETE scripts
└── base.py              # Extend AtomicRedisModel with link support
```

### 6.2 AtomicRedisModel Extensions

```python
class AtomicRedisModel:
    # ... existing code ...

    @classmethod
    def _get_link_fields(cls) -> dict[str, LinkInfo]:
        """Get all Link fields and their configuration."""
        # Introspect model fields for Link types
        pass

    @classmethod
    async def aget(
        cls,
        key: str,
        *,
        fetch_links: bool | list[str] | FetchConfig = False,
        nesting_depth: int = 1,
    ) -> Self | None:
        """Get model by key, optionally fetching links."""
        pass

    async def afetch_links(
        self,
        links: list[str] | None = None,
        nesting_depth: int = 1,
    ) -> Self:
        """Fetch linked models for this instance."""
        pass

    async def adelete(
        self,
        *,
        link_rule: DeleteRules = DeleteRules.DO_NOTHING,
        cascade_links: list[str] | None = None,
    ) -> int:
        """Delete this model, optionally cascading to links."""
        pass
```

---

## 7. Examples

### 7.1 Blog System Example

```python
from rapyer import AtomicRedisModel, Link, Key, DeleteRules
from typing import Annotated

class User(AtomicRedisModel):
    username: Key[str]
    email: str

class Category(AtomicRedisModel):
    name: Key[str]

class Post(AtomicRedisModel):
    title: str
    content: str
    author: Link[User]
    category: Link[Category] | None = None
    tags: list[Link[Category]] = []

# Create models
user = User(username="alice", email="alice@example.com")
await user.asave()

cat = Category(name="tech")
await cat.asave()

post = Post(
    title="Hello World",
    content="My first post",
    author=Link(user),        # From model instance
    category=Link(cat),
    tags=[Link(cat)]
)
await post.asave()

# Fetch without links (default)
post = await Post.aget(post.key)
print(post.author.is_fetched)  # False
print(post.author.key)         # "User:alice"

# Fetch with all links
post = await Post.aget(post.key, fetch_links=True)
print(post.author.is_fetched)  # True
print(post.author.model.email) # "alice@example.com"

# Fetch with specific links only
post = await Post.aget(post.key, fetch_links=["author"])
print(post.author.is_fetched)  # True
print(post.category.is_fetched) # False (not fetched)

# Delete with cascade
await post.adelete(link_rule=DeleteRules.CASCADE)
# This deletes: post (user and category preserved unless configured)
```

### 7.2 Self-Referential Links (Tree Structure)

```python
class Comment(AtomicRedisModel):
    text: str
    author: Link[User]
    parent: Link["Comment"] | None = None  # Forward reference
    replies: list[Link["Comment"]] = []

# Create comment tree
root = Comment(text="Great post!", author=Link(user))
await root.asave()

reply1 = Comment(text="Thanks!", author=Link(user), parent=Link(root))
await reply1.asave()

# Update root with reply
root.replies = [Link(reply1)]
await root.asave()

# Fetch with limited depth to prevent infinite recursion
comment = await Comment.aget(root.key, fetch_links=True, nesting_depth=2)
```

---

## 8. Redis Commands Used

| Operation | Redis Commands | Single Trip? |
|-----------|---------------|--------------|
| Save with links | `JSON.SET` | Yes |
| Get without links | `JSON.GET` | Yes |
| Get with links | Lua script (EVALSHA) | Yes |
| Delete without cascade | `DEL` | Yes |
| Delete with cascade | Lua script (EVALSHA) | Yes |
| Bulk get with links | Lua script (EVALSHA) | Yes |
| Bulk delete cascade | Lua script (EVALSHA) | Yes |

---

## 9. Considerations

### 9.1 Data Consistency

- Links are stored as strings (keys), not embedded documents
- If a linked model is deleted, the link becomes "dangling"
- Consider adding validation on fetch to detect dangling links
- Optionally: maintain back-references for referential integrity

### 9.2 Performance

- **Without links**: Same as current performance (single `JSON.GET`)
- **With links**: Single Lua script call, but script complexity grows with link count
- **Recommendation**: Use `fetch_links` only when needed

### 9.3 Indexing Links

```python
class Post(AtomicRedisModel):
    title: Index[str]
    author: Index[Link[User]]  # Index the key string for searching
```

This allows queries like:
```python
posts = await Post.afind(Post.author == "User:alice")
```

### 9.4 Migrations

Existing models without links continue to work unchanged. Adding a `Link` field is backward-compatible as it's just stored as a string.

---

## 10. Future Enhancements

1. **BackLink**: Virtual reverse references (computed, not stored)
2. **Lazy Loading**: Proxy objects that fetch on attribute access
3. **Link Validation**: Verify linked model exists on save
4. **Batch Operations**: Optimized bulk link fetching
5. **Eager Loading Presets**: Named configurations for common fetch patterns

---

## 11. Summary

This design provides:

- **Type-safe foreign keys** with `Link[Model]` and `list[Link[Model]]`
- **Single-trip extraction** via Lua scripts
- **Single-trip cascade deletion** via Lua scripts
- **Configurable behavior** at field and query level
- **Backward compatibility** with existing models

Sources:
- [Beanie ODM Relations](https://beanie-odm.dev/tutorial/relations/)
- [Beanie GitHub](https://github.com/BeanieODM/beanie)
