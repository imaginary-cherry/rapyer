# Indexing Fields

Rapyer allows you to mark specific fields as indexed, enabling powerful filtering capabilities when querying your models. The `Index` annotation creates Redis Search indices that let you use filter expressions with the `afind()` method.

## Why Index Fields?

By default, Redis stores models as JSON documents that can only be retrieved by their key. When you need to find models based on field values (e.g., "find all users older than 30"), you need to create search indices on those fields.

**Without indexed fields:**
```python
# You can only retrieve by key
user = await User.aget("User:abc123")

# Or get ALL users and filter manually (inefficient)
all_users = await User.afind()
older_users = [u for u in all_users if u.age > 30]
```

**With indexed fields:**
```python
# Efficient server-side filtering
older_users = await User.afind(User.age > 30)
```

## Prerequisites

!!! danger "init_rapyer is Required"
    The `Index` field requires proper initialization using `init_rapyer()`. Without this initialization, indexed fields will not work correctly and filter expressions will fail. Always call `init_rapyer()` before using any models with indexed fields.

```python
from rapyer import init_rapyer

# Must be called before using indexed models
await init_rapyer(redis="redis://localhost:6379/0")
```

!!! danger "Redis Database Limitation"
    Redis Search indices are only supported on database 0 (`db=0`). If you're using a different database number, filtering with expressions will not work. This is a limitation of the Redis Search module.

## Basic Usage

Use the `Index` annotation with `Annotated` to mark fields as searchable:

```python
from rapyer import AtomicRedisModel, Index, init_rapyer
from typing import Annotated

class User(AtomicRedisModel):
    # Indexed fields (searchable with afind expressions)
    name: Annotated[str, Index()]
    age: Index[int]   # This is the same as Annotated[int, Index()]
    email: Index[str]
    status: Index[str] = "active"

    # Non-indexed fields (not searchable)
    internal_notes: str = ""
    metadata: dict = Field(default_factory=dict)

async def main():
    # Initialize rapyer first - REQUIRED for indexed fields
    await init_rapyer(redis="redis://localhost:6379/0")

    # Now you can use filter expressions
    active_users = await User.afind(User.status == "active")
```

## Filtering with afind()

Once fields are indexed, you can use them in filter expressions with `afind()`:

### Comparison Operators

```python
# Equal to
active_users = await User.afind(User.status == "active")

# Not equal to
non_admins = await User.afind(User.role != "admin")

# Greater than
older_users = await User.afind(User.age > 30)

# Less than and equal
young_users = await User.afind(User.age < 25 & User.status != "inactive")

# Greater than or equal
adults = await User.afind(User.age >= 18)

# Less than or equal
affordable = await Product.afind(Product.price <= 100.0)
```

### Logical Operators

```python
# AND - combine conditions with &
young_active = await User.afind(
    (User.age <= 30) & (User.status == "active")
)

# OR - alternative conditions with |
special_users = await User.afind(
    (User.age < 25) | (User.score > 90)
)

# NOT - negate conditions with ~
not_inactive = await User.afind(~(User.status == "inactive"))
```

### Complex Expressions

```python
# Combine multiple operators
results = await User.afind(
    ((User.age >= 25) & (User.age <= 35)) &
    ((User.status == "active") | (User.score >= 80))
)
```

## Supported Field Types

The following field types can be indexed:

| Type | Notes |
|------|-------|
| `str` | Full text and exact matching |
| `int` | Numeric comparison operators |
| `float` | Numeric comparison operators |
| `bool` | Equality comparison |
| `datetime` | Converted to Unix timestamp (see warning below) |

!!! warning "Datetime Indexing and Timezone Information"
    When indexing `datetime` fields, values are stored as Unix timestamps (floats). This means **all timezone information is lost** during conversion. Timestamps represent UTC moments in time, and when retrieved, they are restored as naive datetime objects. If preserving timezone information is critical, consider storing the timezone separately or using string-based datetime storage without indexing.

```python
from datetime import datetime
from typing import Annotated

class Event(AtomicRedisModel):
    name: Annotated[str, Index]
    created_at: Annotated[datetime, Index]  # Stored as Unix timestamp

# Filter by datetime (comparison works on timestamp values)
recent_events = await Event.afind(
    Event.created_at > datetime(2024, 1, 1)
)
```

## Complete Example

```python
import asyncio
from datetime import datetime
from typing import Annotated
from rapyer import AtomicRedisModel, Index, init_rapyer, teardown_rapyer


class User(AtomicRedisModel):
    name: Annotated[str, Index]
    age: Annotated[int, Index]
    email: Annotated[str, Index]
    status: Annotated[str, Index] = "active"
    score: Annotated[float, Index] = 0.0

    # Non-indexed field
    internal_id: str = ""


async def main():
    # Initialize rapyer - REQUIRED for indexed fields
    await init_rapyer(redis="redis://localhost:6379/0")

    try:
        # Create and save users
        users = [
            User(name="Alice", age=25, email="alice@example.com", score=85.5),
            User(name="Bob", age=30, email="bob@example.com", status="inactive", score=92.0),
            User(name="Charlie", age=35, email="charlie@example.com", score=78.3),
            User(name="Diana", age=28, email="diana@example.com", score=95.8)
        ]
        await User.ainsert(*users)

        # Find active users
        active = await User.afind(User.status == "active")
        print(f"Active users: {[u.name for u in active]}")  # Alice, Charlie, Diana

        # Find users older than 27
        older = await User.afind(User.age > 27)
        print(f"Users older than 27: {[u.name for u in older]}")  # Bob, Charlie, Diana

        # Find young active users with high scores
        special = await User.afind(
            (User.age <= 30) & (User.status == "active") & (User.score >= 80)
        )
        print(f"Young active high-scorers: {[u.name for u in special]}")  # Alice, Diana

    finally:
        await teardown_rapyer()


if __name__ == "__main__":
    asyncio.run(main())
```

## Best Practices

1. **Only index fields you need to filter on** - Indexing has storage overhead, so only mark fields as indexed if you'll use them in filter expressions

2. **Initialize early** - Call `init_rapyer()` at application startup before any model operations

3. **Use db=0** - Redis Search only works with database 0

4. **Choose appropriate field types** - Use numeric types for range queries, strings for exact/text matching

5. **Combine with non-indexed fields** - Not every field needs indexing; use regular fields for data that doesn't need filtering

## When NOT to Use Index

- **Fields never used in queries** - Don't index fields you only read/write directly
- **High-cardinality unique fields** - If every value is unique (like UUIDs), consider using `Key` instead
- **Large text fields** - Very large strings may impact index performance
- **Frequently updated fields** - Index updates have a small overhead on writes
