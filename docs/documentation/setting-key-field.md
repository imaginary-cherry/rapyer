# Key Field

Rapyer provides special field annotations that modify how your models interact with Redis. These fields give you additional control over model behavior.
The `Key` field annotation allows you to specify a custom field to act as the primary key instead of Rapyer's automatically generated primary key. When you use a `Key` field, it overrides the value of the model's `pk` property. This is useful when you have meaningful identifiers like user IDs, email addresses, or timestamps that should serve as unique identifiers.

**⚠️ Warning**: Using custom key fields is usually not recommended. The automatic primary key generation is optimized for Redis operations and handles uniqueness automatically. Only use custom keys when you have a specific business requirement for meaningful identifiers.

### Basic Usage

```python
from rapyer import AtomicRedisModel
from rapyer.fields import Key

class User(AtomicRedisModel):
    user_id: Key(str)  # This field will be used as the primary key
    name: str
    email: str
    age: int = 25
```

### Alternative Syntax with Annotated

```python
from typing import Annotated
from datetime import datetime
from rapyer import AtomicRedisModel
from rapyer.fields import Key

class Event(AtomicRedisModel):
    created_at: Annotated[datetime, Key()]  # datetime as primary key
    event_name: str
    description: str
    duration_minutes: int = 60
```

### Examples

#### User with Email as Key

```python
from rapyer.fields import Key

class User(AtomicRedisModel):
    email: Key(str)  # Email serves as the unique identifier
    name: str
    age: int
    preferences: dict = {}

# Usage
user = User(email="alice@example.com", name="Alice", age=30)
await user.asave()  # Stored with email as the Redis key
```

#### Log Entry with Timestamp Key

```python
from datetime import datetime
from rapyer.fields import Key

class LogEntry(AtomicRedisModel):
    timestamp: Key(datetime)
    level: str
    message: str
    source: str

# Usage
log = LogEntry(
    timestamp=datetime.now(),
    level="INFO",
    message="Application started",
    source="main.py"
)
await log.asave()  # Stored with timestamp as the Redis key
```

#### Product with SKU Key

```python
from rapyer.fields import Key

class Product(AtomicRedisModel):
    sku: Key(str)  # Product SKU as primary key
    name: str
    price: float
    category: str

# Usage
product = Product(
    sku="LAPTOP-2024-001",
    name="Gaming Laptop",
    price=1299.99,
    category="Electronics"
)
await product.asave()
```

## Important Considerations

### Key Uniqueness

Ensure your custom key field values are guaranteed to be unique across all instances:

```python
# ✅ Good: Emails are naturally unique
class User(AtomicRedisModel):
    email: Key(str)  # Safe choice
    name: str

# ⚠️ Risky: Names might not be unique
class User(AtomicRedisModel):
    name: Key(str)    # Could cause conflicts!
    email: str
```

### Immutability

Custom key field values should never change after the model is saved. Changing the key value can lead to unexpected behavior:

```python
user = User(email="john@example.com", name="John")
await user.asave()

# ❌ Avoid changing the key field value
user.email = "john.doe@example.com"  # This changes the primary key!
await user.asave()  # This might create a new record instead of updating
```

### Performance Impact

- Custom keys have the same performance as auto-generated keys
- The key field is used directly in Redis operations
- No additional overhead is introduced by using custom keys

### Migration Considerations

If you need to add a custom key to an existing model:

1. **Data Migration**: Existing records will continue using auto-generated keys
2. **Backward Compatibility**: New records will use the custom key field
3. **Gradual Migration**: Consider migrating data in batches if needed

```python
# Before: Using auto-generated keys
class User(AtomicRedisModel):
    name: str
    email: str

# After: Adding custom key (existing records keep auto-generated keys)
class User(AtomicRedisModel):
    email: Key(str)  # New records will use email as key
    name: str
```

## Best Practices

1. **Choose Stable Values**: Use fields that won't change over the model's lifetime
2. **Ensure Uniqueness**: Verify that key field values are guaranteed to be unique
3. **Document Intent**: Clearly document why a custom key is necessary
4. **Test Thoroughly**: Ensure your application handles key-based operations correctly
5. **Consider Alternatives**: Evaluate whether the automatic primary key generation meets your needs
6. **Use Sparingly**: Only implement custom keys when there's a clear business requirement

## When NOT to Use Custom Keys

- **Auto-incrementing IDs**: Redis doesn't natively support auto-increment
- **Non-unique values**: Any field that might have duplicate values
- **Frequently changing values**: Fields that might need updates
- **Complex composite keys**: Redis works best with simple string keys
- **Default use cases**: When the automatic primary key generation works fine