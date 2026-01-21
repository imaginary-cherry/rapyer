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

### 2.1 Core Link Class with Seamless Attribute Access

The Link class acts as a **transparent proxy** to the underlying model. Once fetched, you can access model attributes directly through the link without needing `.model`:

```python
# After fetching, these are equivalent:
book.author.name          # Seamless access (preferred)
book.author.model.name    # Explicit access (also works)
```

```python
from typing import Generic, TypeVar, TYPE_CHECKING, Any
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

M = TypeVar("M", bound="AtomicRedisModel")

class LinkNotFetchedError(Exception):
    """Raised when accessing attributes on an unfetched link."""
    pass

class Link(Generic[M]):
    """
    A foreign key reference to another AtomicRedisModel.

    When not fetched: stores the key string (e.g., "Author:uuid")
    When fetched: stores the actual model instance

    Provides seamless attribute access - once fetched, you can access
    the linked model's attributes directly:

        book.author.name  # Works directly after fetch_links=True
    """

    # Note: Can't use __slots__ with __getattr__ proxy pattern effectively
    _key: str
    _model: M | None
    _model_class: type[M] | None
    _is_fetched: bool

    def __init__(
        self,
        ref: str | M,
        model_class: type[M] | None = None
    ):
        # Use object.__setattr__ to avoid triggering __setattr__ if we add it
        object.__setattr__(self, "_model_class", model_class)

        if isinstance(ref, str):
            object.__setattr__(self, "_key", ref)
            object.__setattr__(self, "_model", None)
            object.__setattr__(self, "_is_fetched", False)
        else:
            # ref is a model instance
            object.__setattr__(self, "_key", ref.key)
            object.__setattr__(self, "_model", ref)
            object.__setattr__(self, "_is_fetched", True)

    @property
    def key(self) -> str:
        """The Redis key of the linked model."""
        return self._key

    @property
    def pk(self) -> str:
        """The primary key (ID portion) of the linked model."""
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

    def __getattr__(self, name: str) -> Any:
        """
        Proxy attribute access to the underlying model.

        This enables seamless access like:
            book.author.name  # instead of book.author.model.name
        """
        # Avoid infinite recursion for private attributes
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

        if not self._is_fetched:
            raise LinkNotFetchedError(
                f"Cannot access '{name}' on unfetched Link[{self._model_class.__name__ if self._model_class else 'Model'}]. "
                f"Use fetch_links=True when fetching, or await link.afetch() first. "
                f"Link key: '{self._key}'"
            )

        if self._model is None:
            raise LinkNotFetchedError(
                f"Link to '{self._key}' was fetched but model not found (dangling reference)."
            )

        return getattr(self._model, name)

    def __repr__(self) -> str:
        if self._is_fetched:
            return f"Link({self._model!r})"
        return f"Link('{self._key}')"

    def __eq__(self, other) -> bool:
        """Compare links by their key."""
        if isinstance(other, Link):
            return self._key == other._key
        if isinstance(other, str):
            return self._key == other
        if hasattr(other, "key"):
            return self._key == other.key
        return False

    def __hash__(self) -> int:
        return hash(self._key)

    async def afetch(self, fetch_links: "LinkFetchConfig | None" = None) -> M:
        """
        Fetch the linked model from Redis.

        Args:
            fetch_links: Optional nested fetch configuration for the linked model's links.

        Returns:
            The fetched model instance.
        """
        if not self._is_fetched:
            self._model = await self._model_class.aget(
                self._key,
                fetch_links=fetch_links
            )
            object.__setattr__(self, "_is_fetched", True)
        return self._model

    def _set_fetched_model(self, model: M) -> None:
        """Internal method to set the fetched model (used by fetch system)."""
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_is_fetched", True)

    # Pydantic integration
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        from typing import get_args
        args = get_args(source_type)
        model_class = args[0] if args else None

        def validate_link(value) -> Link:
            if isinstance(value, Link):
                return value
            if isinstance(value, str):
                return Link(value, model_class=model_class)
            if hasattr(value, "key"):
                return Link(value, model_class=model_class)
            raise ValueError(f"Cannot create Link from {type(value)}")

        def serialize_link(link: Link, info) -> str:
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

### 2.2 Seamless Access Examples

```python
class Author(AtomicRedisModel):
    name: str
    email: str
    bio: str

class Publisher(AtomicRedisModel):
    name: str
    country: str

class Book(AtomicRedisModel):
    title: str
    author: Link[Author]
    publisher: Link[Publisher]

# Fetch book with links
book = await Book.aget("Book:123", fetch_links=True)

# Seamless attribute access - NO .model needed!
print(book.author.name)        # "F. Scott Fitzgerald"
print(book.author.email)       # "fscott@example.com"
print(book.publisher.country)  # "USA"

# These also work but are more verbose:
print(book.author.model.name)  # Same result

# Check if fetched before accessing (optional)
if book.author.is_fetched:
    print(book.author.bio)

# Error if not fetched:
book2 = await Book.aget("Book:456")  # No fetch_links
book2.author.name  # Raises LinkNotFetchedError with helpful message
```

---

## 3. Extraction (Fetching Linked Models)

### 3.1 Basic API

```python
# Fetch a single model with ALL its links populated (1 level deep)
book = await Book.aget("Book:123", fetch_links=True)
print(book.author.name)  # "F. Scott Fitzgerald" (seamless access!)

# Fetch with selective links (only specified fields)
book = await Book.aget("Book:123", fetch_links=["author"])

# Bulk fetch with links
books = await Book.afind(fetch_links=True)

# Instance method to fetch links after initial load
book = await Book.aget("Book:123")  # Links not fetched
await book.afetch_links()           # Now fetch all links
await book.afetch_links(["author"]) # Or fetch specific links
```

### 3.2 Nested Link Configuration (Deep Fetching)

The key feature: **configure which nested links to fetch at each level**.

```python
from rapyer import LinkFetchConfig

# Type alias for readability
LinkFetchConfig = bool | list[str] | dict[str, "LinkFetchConfig"]
```

#### 3.2.1 Simple Nested Fetch

```python
class Country(AtomicRedisModel):
    name: str

class Publisher(AtomicRedisModel):
    name: str
    country: Link[Country]

class Author(AtomicRedisModel):
    name: str
    publisher: Link[Publisher]

class Book(AtomicRedisModel):
    title: str
    author: Link[Author]
    publisher: Link[Publisher]

# Fetch book -> author -> publisher -> country (3 levels deep!)
book = await Book.aget(
    "Book:123",
    fetch_links={
        "author": {                    # Fetch author
            "publisher": {             # Also fetch author's publisher
                "country": True        # Also fetch publisher's country
            }
        },
        "publisher": True              # Fetch book's direct publisher (1 level)
    }
)

# Now all these work seamlessly:
print(book.title)                           # "The Great Gatsby"
print(book.author.name)                     # "F. Scott Fitzgerald"
print(book.author.publisher.name)           # "Scribner"
print(book.author.publisher.country.name)   # "USA"
print(book.publisher.name)                  # "Scribner" (direct link)
print(book.publisher.country.is_fetched)    # False (not configured to fetch)
```

#### 3.2.2 Fetch Config Options

```python
# Option 1: True = fetch this link only (no nested links)
fetch_links=True                     # All direct links, 1 level
fetch_links={"author": True}         # Only author, 1 level

# Option 2: List = fetch these specific links only
fetch_links=["author", "publisher"]  # These two links, 1 level

# Option 3: Dict = nested configuration per field
fetch_links={
    "author": True,                  # Fetch author (no nested)
    "publisher": {                   # Fetch publisher AND its nested links
        "country": True,
        "contacts": True
    },
    "reviews": {                     # Fetch reviews AND their authors
        "author": True
    }
}

# Option 4: "*" wildcard = all links at this level
fetch_links={
    "author": {
        "*": True                    # Fetch ALL of author's links
    }
}

# Option 5: Recursive depth limit for self-referential
fetch_links={
    "replies": {
        "__depth__": 3,              # Max 3 levels of nested replies
        "author": True               # Fetch author at each level
    }
}
```

#### 3.2.3 Complex Example: Blog with Comments

```python
class User(AtomicRedisModel):
    username: Key[str]
    profile_picture: Link[Image] | None = None

class Comment(AtomicRedisModel):
    text: str
    author: Link[User]
    replies: list[Link["Comment"]] = []  # Self-referential

class Post(AtomicRedisModel):
    title: str
    author: Link[User]
    comments: list[Link[Comment]] = []

# Fetch post with:
# - Author (with profile picture)
# - Comments (with authors, and 2 levels of replies with their authors)
post = await Post.aget(
    "Post:123",
    fetch_links={
        "author": {
            "profile_picture": True
        },
        "comments": {
            "author": {
                "profile_picture": True
            },
            "replies": {
                "__depth__": 2,          # 2 levels of nested replies
                "author": True           # Fetch author for each reply
            }
        }
    }
)

# All seamless access:
print(post.author.username)                          # "alice"
print(post.author.profile_picture.url)               # "/images/alice.jpg"
print(post.comments[0].text)                         # "Great post!"
print(post.comments[0].author.username)              # "bob"
print(post.comments[0].replies[0].text)              # "Thanks!"
print(post.comments[0].replies[0].author.username)   # "alice"
```

### 3.3 FetchConfig Class

```python
from dataclasses import dataclass, field
from typing import Literal

# Recursive type for nested fetch configuration
LinkFetchConfig = bool | list[str] | dict[str, "LinkFetchConfig | DepthConfig"]

@dataclass
class DepthConfig:
    """Configuration for recursive/self-referential links."""
    depth: int = 1
    """Maximum recursion depth."""

    fetch_links: LinkFetchConfig = True
    """What to fetch at each level."""

# Alternative: use special keys in dict
# "__depth__": 3  -> max depth
# "__all__": True -> fetch all links at this level
# "*": {...}      -> apply config to all links
```

### 3.4 Lua Script for Atomic Nested Fetch

The script recursively fetches linked models based on the nested configuration, all in a **single Redis round-trip**.

```lua
-- FETCH_WITH_NESTED_LINKS_SCRIPT
-- KEYS[1] = main model key
-- ARGV[1] = JSON-encoded fetch configuration (nested dict)
-- Returns: JSON object with main model and all linked models by key

local main_key = KEYS[1]
local fetch_config = cjson.decode(ARGV[1])
local result = {
    __models__ = {}  -- key -> model data
}
local visited = {}  -- Prevent infinite loops

-- Helper: Get value at path in object
local function get_at_path(obj, field_name)
    if obj and type(obj) == "table" then
        return obj[field_name]
    end
    return nil
end

-- Helper: Check if value looks like a Redis key (has ":")
local function is_redis_key(value)
    return type(value) == "string" and string.find(value, ":") ~= nil
end

-- Recursive fetch function
local function fetch_with_config(key, config, depth)
    -- Depth limit check
    if depth > 20 then return end  -- Safety limit

    -- Already visited check
    if visited[key] then return end
    visited[key] = true

    -- Fetch the model
    local data = redis.call('JSON.GET', key)
    if not data or data == 'null' then
        return
    end

    local obj = cjson.decode(data)

    -- Handle array wrapping from Redis JSON
    if type(obj) == "table" and obj[1] and not obj[2] then
        obj = obj[1]
    end

    result.__models__[key] = obj

    -- If config is false or nil, don't fetch nested
    if not config or config == false then
        return
    end

    -- If config is true, stop here (only fetch this level)
    if config == true then
        return
    end

    -- If config is a list, convert to dict with true values
    if type(config) == "table" and config[1] then
        local dict_config = {}
        for _, field in ipairs(config) do
            dict_config[field] = true
        end
        config = dict_config
    end

    -- Config is a dict - process each field
    if type(config) == "table" then
        -- Check for depth limit in config
        local max_depth = config["__depth__"]
        if max_depth and depth >= max_depth then
            return
        end

        -- Check for wildcard "*" (fetch all links)
        local wildcard_config = config["*"]

        for field_name, field_config in pairs(config) do
            -- Skip special keys
            if field_name:sub(1, 2) ~= "__" and field_name ~= "*" then
                local value = get_at_path(obj, field_name)

                if value then
                    if is_redis_key(value) then
                        -- Single link
                        fetch_with_config(value, field_config, depth + 1)
                    elseif type(value) == "table" then
                        -- List of links
                        for _, link_key in ipairs(value) do
                            if is_redis_key(link_key) then
                                fetch_with_config(link_key, field_config, depth + 1)
                            end
                        end
                    end
                end
            end
        end

        -- Handle wildcard if present
        if wildcard_config then
            for field_name, value in pairs(obj) do
                if not config[field_name] then  -- Not already processed
                    if is_redis_key(value) then
                        fetch_with_config(value, wildcard_config, depth + 1)
                    elseif type(value) == "table" then
                        for _, link_key in ipairs(value) do
                            if is_redis_key(link_key) then
                                fetch_with_config(link_key, wildcard_config, depth + 1)
                            end
                        end
                    end
                end
            end
        end

        -- Handle self-referential with __self__
        local self_config = config["__self__"]
        if self_config then
            -- Re-apply same config to this model type
            -- The field that triggered this would need special handling
        end
    end
end

-- Start recursive fetch
fetch_with_config(main_key, fetch_config, 0)

return cjson.encode(result)
```

### 3.5 Python-Side Processing

After the Lua script returns all models, Python reassembles them:

```python
async def _fetch_with_links(
    cls,
    key: str,
    fetch_links: LinkFetchConfig
) -> Self:
    """Fetch model with nested links in single Redis trip."""

    # Convert config to JSON for Lua
    config_json = json.dumps(_normalize_fetch_config(fetch_links))

    # Execute Lua script
    result_json = await cls.Meta.redis.evalsha(
        FETCH_NESTED_LINKS_SHA,
        1,  # num keys
        key,
        config_json
    )

    if not result_json:
        return None

    result = json.loads(result_json)
    models_data = result["__models__"]

    # Build model instances and populate links
    models_cache = {}  # key -> model instance

    for model_key, model_data in models_data.items():
        model_class = _get_model_class_from_key(model_key)
        models_cache[model_key] = model_class.model_validate(model_data)

    # Now populate Link objects with fetched models
    main_model = models_cache[key]
    _populate_links(main_model, models_cache, fetch_links)

    return main_model

def _populate_links(model, cache, config):
    """Recursively populate Link fields with cached models."""
    for field_name, field_info in model.model_fields.items():
        if _is_link_field(field_info):
            link = getattr(model, field_name)
            if link and link.key in cache:
                link._set_fetched_model(cache[link.key])
                # Recursively populate nested links
                if isinstance(config, dict) and field_name in config:
                    _populate_links(link.model, cache, config[field_name])
```

---

## 4. Deletion with Cascade

### 4.1 Basic Delete API

```python
# Delete just the book (default - no cascade)
await book.adelete()

# Delete book and cascade to ALL linked models
await book.adelete(cascade_links=True)

# Delete with selective cascade - only specific fields
await book.adelete(cascade_links=["drafts", "attachments"])
```

### 4.2 Nested Cascade Configuration

Just like fetching, you can configure **which nested links to cascade delete**:

```python
# Type alias (same as fetch)
LinkCascadeConfig = bool | list[str] | dict[str, "LinkCascadeConfig"]
```

#### 4.2.1 Cascade Examples

```python
class Image(AtomicRedisModel):
    url: str

class Draft(AtomicRedisModel):
    content: str
    attachments: list[Link[Image]] = []

class Book(AtomicRedisModel):
    title: str
    author: Link[Author]           # Don't delete authors!
    cover: Link[Image] | None      # Delete cover image
    drafts: list[Link[Draft]] = [] # Delete drafts and their attachments

# Delete book only (no cascade)
await book.adelete()
# Result: Only book deleted. Author, cover, drafts all preserved.

# Delete book + cover image only
await book.adelete(cascade_links=["cover"])
# Result: Book and cover image deleted. Author and drafts preserved.

# Delete book + drafts (but not draft attachments)
await book.adelete(cascade_links={"drafts": True})
# Result: Book and drafts deleted. Draft attachments preserved.

# Delete book + drafts + draft attachments (nested cascade)
await book.adelete(
    cascade_links={
        "cover": True,              # Delete cover
        "drafts": {                 # Delete drafts AND...
            "attachments": True     # ...their attachments
        }
        # "author" not listed = preserved
    }
)
# Result: Book, cover, all drafts, all draft attachments deleted.
#         Author preserved.
```

#### 4.2.2 Self-Referential Cascade with Depth Limit

```python
class Comment(AtomicRedisModel):
    text: str
    author: Link[User]
    replies: list[Link["Comment"]] = []

# Delete comment and ALL nested replies (recursive)
await comment.adelete(
    cascade_links={
        "replies": {
            "__depth__": 10,        # Max recursion depth
            "__self__": True        # Continue cascading to nested replies
        }
        # "author" not listed = users preserved
    }
)

# Shorthand for unlimited depth on self-referential:
await comment.adelete(
    cascade_links={
        "replies": "__cascade_recursive__"
    }
)
```

#### 4.2.3 Complex Cascade Example

```python
class Post(AtomicRedisModel):
    title: str
    author: Link[User]
    cover_image: Link[Image] | None = None
    comments: list[Link[Comment]] = []
    tags: list[Link[Tag]] = []

# Delete post with fine-grained cascade control:
await post.adelete(
    cascade_links={
        # Delete cover image
        "cover_image": True,

        # Delete comments, their replies (2 levels), but preserve comment authors
        "comments": {
            "replies": {
                "__depth__": 2,
                # Don't cascade to reply authors
            }
            # "author" not listed = comment authors preserved
        },

        # Don't delete tags (not listed)
        # Don't delete post author (not listed)
    }
)
```

### 4.3 Bulk Delete with Cascade

```python
# Delete multiple books with same cascade config
await Book.adelete_many(
    ["Book:1", "Book:2", "Book:3"],
    cascade_links={
        "drafts": {"attachments": True},
        "cover": True
    }
)

# Delete by query with cascade
await Book.adelete_where(
    Book.status == "archived",
    cascade_links=["drafts"]
)
```

### 4.4 Safety Features

```python
# Dry run - see what would be deleted without actually deleting
keys_to_delete = await book.adelete(
    cascade_links={"drafts": {"attachments": True}},
    dry_run=True
)
print(keys_to_delete)
# ["Book:123", "Draft:456", "Draft:789", "Image:abc", "Image:def"]

# Confirm before delete (useful for CLI/scripts)
await book.adelete(
    cascade_links=True,
    confirm=True  # Raises if not confirmed
)
```

### 4.5 Lua Script for Atomic Nested Cascade Delete

The script traverses the nested cascade configuration and deletes all matching models atomically.

```lua
-- CASCADE_DELETE_NESTED_SCRIPT
-- KEYS[1] = main model key
-- ARGV[1] = JSON-encoded cascade configuration (nested dict)
-- ARGV[2] = dry_run flag ("true" or "false")
-- Returns: JSON array of deleted keys (or keys that would be deleted)

local main_key = KEYS[1]
local cascade_config = cjson.decode(ARGV[1])
local dry_run = ARGV[2] == "true"

local keys_to_delete = {}
local visited = {}

-- Helper: Check if value looks like a Redis key
local function is_redis_key(value)
    return type(value) == "string" and string.find(value, ":") ~= nil
end

-- Recursive collection function
local function collect_keys(key, config, depth)
    -- Safety limit
    if depth > 50 then return end

    -- Already visited
    if visited[key] then return end
    visited[key] = true

    -- Add this key to delete list
    table.insert(keys_to_delete, key)

    -- If no cascade config, stop here
    if not config or config == false then
        return
    end

    -- If config is just "true", delete this but don't cascade further
    if config == true then
        return
    end

    -- Fetch model data to find nested links
    local data = redis.call('JSON.GET', key)
    if not data or data == 'null' then
        return
    end

    local obj = cjson.decode(data)
    if type(obj) == "table" and obj[1] and not obj[2] then
        obj = obj[1]
    end

    -- Handle list config -> convert to dict
    if type(config) == "table" and config[1] then
        local dict_config = {}
        for _, field in ipairs(config) do
            dict_config[field] = true
        end
        config = dict_config
    end

    -- Process nested cascade config
    if type(config) == "table" then
        local max_depth = config["__depth__"]
        if max_depth and depth >= max_depth then
            return
        end

        -- Special: __cascade_recursive__ for self-referential
        for field_name, field_config in pairs(config) do
            if field_name:sub(1, 2) ~= "__" then
                local value = obj[field_name]

                -- Handle recursive marker
                local actual_config = field_config
                if field_config == "__cascade_recursive__" then
                    -- Re-use same config for this field
                    actual_config = config
                end

                if value then
                    if is_redis_key(value) then
                        -- Single link
                        collect_keys(value, actual_config, depth + 1)
                    elseif type(value) == "table" then
                        -- List of links
                        for _, link_key in ipairs(value) do
                            if is_redis_key(link_key) then
                                collect_keys(link_key, actual_config, depth + 1)
                            end
                        end
                    end
                end
            end
        end
    end
end

-- Collect all keys to delete starting from main key
-- Pass 'true' as initial config to include the main key itself
collect_keys(main_key, true, 0)

-- Remove main key's 'true' and re-collect with actual config
keys_to_delete = {}
visited = {}
table.insert(keys_to_delete, main_key)
visited[main_key] = true

-- Now collect cascaded keys
local data = redis.call('JSON.GET', main_key)
if data and data ~= 'null' then
    local obj = cjson.decode(data)
    if type(obj) == "table" and obj[1] and not obj[2] then
        obj = obj[1]
    end

    if type(cascade_config) == "table" then
        for field_name, field_config in pairs(cascade_config) do
            if field_name:sub(1, 2) ~= "__" then
                local value = obj[field_name]
                if value then
                    if is_redis_key(value) then
                        collect_keys(value, field_config, 1)
                    elseif type(value) == "table" then
                        for _, link_key in ipairs(value) do
                            if is_redis_key(link_key) then
                                collect_keys(link_key, field_config, 1)
                            end
                        end
                    end
                end
            end
        end
    elseif cascade_config == true then
        -- Delete all links (1 level)
        for field_name, value in pairs(obj) do
            if is_redis_key(value) then
                if not visited[value] then
                    visited[value] = true
                    table.insert(keys_to_delete, value)
                end
            elseif type(value) == "table" then
                for _, link_key in ipairs(value) do
                    if is_redis_key(link_key) and not visited[link_key] then
                        visited[link_key] = true
                        table.insert(keys_to_delete, link_key)
                    end
                end
            end
        end
    end
end

-- Execute deletion (or just return list for dry run)
if not dry_run then
    for _, del_key in ipairs(keys_to_delete) do
        redis.call('DEL', del_key)
    end
end

return cjson.encode(keys_to_delete)
```

### 4.6 Python Implementation

```python
async def adelete(
    self,
    *,
    cascade_links: LinkCascadeConfig = False,
    dry_run: bool = False
) -> list[str]:
    """
    Delete this model, optionally cascading to linked models.

    Args:
        cascade_links: Configuration for which links to cascade delete.
            - False: Only delete this model (default)
            - True: Delete this model and all direct links (1 level)
            - ["field1", "field2"]: Delete specific link fields
            - {"field": {"nested": True}}: Nested cascade configuration

        dry_run: If True, return keys that would be deleted without deleting.

    Returns:
        List of keys that were deleted (or would be deleted if dry_run).

    Examples:
        # Delete only this model
        await book.adelete()

        # Delete book and all its direct links
        await book.adelete(cascade_links=True)

        # Delete book and specific links with nesting
        await book.adelete(cascade_links={
            "drafts": {"attachments": True},  # Delete drafts and their attachments
            "cover": True                      # Delete cover image
        })

        # Preview what would be deleted
        keys = await book.adelete(cascade_links=True, dry_run=True)
        print(f"Would delete: {keys}")
    """
    if not cascade_links:
        # Simple delete, no cascade
        await self.Meta.redis.delete(self.key)
        return [self.key]

    # Use Lua script for atomic cascade delete
    config_json = json.dumps(_normalize_cascade_config(cascade_links))
    result_json = await self.Meta.redis.evalsha(
        CASCADE_DELETE_NESTED_SHA,
        1,
        self.key,
        config_json,
        "true" if dry_run else "false"
    )

    return json.loads(result_json)
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
from rapyer import AtomicRedisModel, Link, Key
from typing import Annotated

class User(AtomicRedisModel):
    username: Key[str]
    email: str
    avatar: Link["Image"] | None = None

class Image(AtomicRedisModel):
    url: str
    size: int

class Category(AtomicRedisModel):
    name: Key[str]

class Post(AtomicRedisModel):
    title: str
    content: str
    author: Link[User]
    cover: Link[Image] | None = None
    category: Link[Category] | None = None
    tags: list[Link[Category]] = []

# Create models
avatar = Image(url="/avatars/alice.jpg", size=1024)
await avatar.asave()

user = User(username="alice", email="alice@example.com", avatar=Link(avatar))
await user.asave()

cover = Image(url="/covers/post1.jpg", size=2048)
await cover.asave()

cat = Category(name="tech")
await cat.asave()

post = Post(
    title="Hello World",
    content="My first post",
    author=Link(user),        # From model instance
    cover=Link(cover),
    category=Link(cat),
    tags=[Link(cat)]
)
await post.asave()

# ===== FETCHING =====

# Fetch without links (default)
post = await Post.aget(post.key)
print(post.author.is_fetched)  # False
print(post.author.key)         # "User:alice"
# post.author.email            # Raises LinkNotFetchedError!

# Fetch with all direct links (1 level)
post = await Post.aget(post.key, fetch_links=True)
print(post.author.email)       # "alice@example.com" (seamless!)
print(post.cover.url)          # "/covers/post1.jpg"
print(post.author.avatar.is_fetched)  # False (nested link not fetched)

# Fetch with NESTED links
post = await Post.aget(
    post.key,
    fetch_links={
        "author": {
            "avatar": True     # Also fetch author's avatar
        },
        "cover": True,
        "category": True
    }
)
print(post.author.email)           # "alice@example.com"
print(post.author.avatar.url)      # "/avatars/alice.jpg" (nested!)
print(post.author.avatar.size)     # 1024

# Fetch specific links only
post = await Post.aget(post.key, fetch_links=["author"])
print(post.author.is_fetched)      # True
print(post.category.is_fetched)    # False (not requested)

# ===== DELETING =====

# Delete only the post
await post.adelete()
# Result: Post deleted. Author, cover, category all preserved.

# Delete post and cover image
await post.adelete(cascade_links=["cover"])
# Result: Post and cover deleted. Author, category preserved.

# Delete post and all direct links
await post.adelete(cascade_links=True)
# Result: Post, cover, category deleted. Author preserved (referenced elsewhere).

# Preview deletion (dry run)
keys = await post.adelete(cascade_links=True, dry_run=True)
print(keys)  # ["Post:xxx", "Image:yyy", "Category:tech"]
```

### 7.2 Self-Referential Links (Comment Tree)

```python
class Comment(AtomicRedisModel):
    text: str
    author: Link[User]
    parent: Link["Comment"] | None = None
    replies: list[Link["Comment"]] = []

# Create comment tree
root = Comment(text="Great post!", author=Link(user))
await root.asave()

reply1 = Comment(text="Thanks!", author=Link(user), parent=Link(root))
await reply1.asave()

reply2 = Comment(text="Agreed!", author=Link(user), parent=Link(root))
await reply2.asave()

nested_reply = Comment(text="Me too!", author=Link(user), parent=Link(reply1))
await nested_reply.asave()

# Update parents with replies
reply1.replies = [Link(nested_reply)]
await reply1.asave()

root.replies = [Link(reply1), Link(reply2)]
await root.asave()

# Fetch with nested depth configuration
comment = await Comment.aget(
    root.key,
    fetch_links={
        "author": True,
        "replies": {
            "__depth__": 3,    # Max 3 levels of nested replies
            "author": True,    # Fetch author at each level
            "replies": {       # Recursive config for nested replies
                "__depth__": 2,
                "author": True
            }
        }
    }
)

# Seamless access at all levels!
print(comment.text)                              # "Great post!"
print(comment.author.username)                   # "alice"
print(comment.replies[0].text)                   # "Thanks!"
print(comment.replies[0].author.username)        # "alice"
print(comment.replies[0].replies[0].text)        # "Me too!"
print(comment.replies[0].replies[0].author.username)  # "alice"

# Delete comment and ALL nested replies
await comment.adelete(
    cascade_links={
        "replies": "__cascade_recursive__"  # Recursively delete all replies
        # "author" not listed = users preserved
    }
)
# Result: root, reply1, reply2, nested_reply all deleted. Users preserved.
```

### 7.3 E-commerce Example (Complex Nested)

```python
class Manufacturer(AtomicRedisModel):
    name: str
    country: Link["Country"]

class Country(AtomicRedisModel):
    name: Key[str]
    code: str

class ProductImage(AtomicRedisModel):
    url: str
    alt_text: str

class Product(AtomicRedisModel):
    name: str
    price: float
    manufacturer: Link[Manufacturer]
    images: list[Link[ProductImage]] = []

class OrderItem(AtomicRedisModel):
    product: Link[Product]
    quantity: int

class Order(AtomicRedisModel):
    customer: Link[User]
    items: list[Link[OrderItem]] = []
    status: str = "pending"

# Fetch order with DEEP nested links
order = await Order.aget(
    order_key,
    fetch_links={
        "customer": {
            "avatar": True
        },
        "items": {
            "product": {
                "manufacturer": {
                    "country": True  # 4 levels deep!
                },
                "images": True
            }
        }
    }
)

# All seamless access:
print(order.customer.username)
print(order.customer.avatar.url)
print(order.items[0].quantity)
print(order.items[0].product.name)
print(order.items[0].product.price)
print(order.items[0].product.manufacturer.name)
print(order.items[0].product.manufacturer.country.name)
print(order.items[0].product.images[0].url)

# Delete order with selective cascade
await order.adelete(
    cascade_links={
        "items": {
            # Delete order items, but preserve products
            # (products are catalog items, not order-specific)
        }
    }
)
# Result: Order and OrderItems deleted. Products, manufacturer, etc. preserved.
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

### Core Features

| Feature | Description |
|---------|-------------|
| **Type-safe foreign keys** | `Link[Model]` and `list[Link[Model]]` with full Pydantic v2 validation |
| **Seamless attribute access** | `book.author.name` works directly (no `.model` needed) |
| **Single-trip extraction** | Lua script fetches all nested links atomically |
| **Single-trip cascade deletion** | Lua script deletes all configured links atomically |
| **Nested configuration** | Fine-grained control over which links to fetch/delete at each level |
| **Self-referential support** | Depth limits and recursive configuration for tree structures |

### Configuration Types

```python
# Both fetch_links and cascade_links accept:
LinkConfig = (
    bool |                      # True = all direct links, False = none
    list[str] |                 # ["field1", "field2"] = specific fields
    dict[str, "LinkConfig"]     # Nested configuration per field
)

# Special dict keys:
# "__depth__": int         - Max recursion depth
# "__cascade_recursive__"  - Self-referential cascade
# "*": LinkConfig          - Wildcard (all fields)
```

### API Quick Reference

```python
# Fetching
model = await Model.aget(key, fetch_links=True)           # All direct links
model = await Model.aget(key, fetch_links=["author"])     # Specific links
model = await Model.aget(key, fetch_links={               # Nested
    "author": {"avatar": True}
})

# Deleting
await model.adelete()                                      # Just this model
await model.adelete(cascade_links=True)                   # + all direct links
await model.adelete(cascade_links=["drafts"])             # + specific links
await model.adelete(cascade_links={                       # Nested cascade
    "drafts": {"attachments": True}
})
await model.adelete(cascade_links=True, dry_run=True)     # Preview

# Seamless access after fetch
model.link_field.nested_attribute  # Works directly!
```

### Redis Efficiency

| Operation | Redis Round-Trips |
|-----------|-------------------|
| `aget(key)` | 1 |
| `aget(key, fetch_links=True)` | 1 (Lua script) |
| `aget(key, fetch_links={nested...})` | 1 (Lua script) |
| `adelete()` | 1 |
| `adelete(cascade_links={nested...})` | 1 (Lua script) |

---

Sources:
- [Beanie ODM Relations](https://beanie-odm.dev/tutorial/relations/)
- [Beanie GitHub](https://github.com/BeanieODM/beanie)
