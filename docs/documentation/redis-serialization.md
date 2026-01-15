# Redis Serialization

Rapyer uses Pydantic's native serialization to convert model data to JSON format for Redis storage.

## Default Behavior

By default, Rapyer handles field serialization in two ways:

1. **Redis-native types** - Fields using [Redis Types](redis-types.md) (`str`, `int`, `float`, `list`, `dict`, nested models) are serialized directly to JSON
2. **Non-supported types** - Fields with types that Redis doesn't natively support (enums, custom classes, `type` objects) are pickled and stored as base64-encoded strings

```python
from enum import Enum
from rapyer import AtomicRedisModel

class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class User(AtomicRedisModel):
    name: str              # Stored as JSON string
    status: Status = Status.ACTIVE  # Pickled by default
```

With the default behavior, the `status` field is stored as a pickled value like `"gASVFgAAAAAAAACMCF9fbWFpbl9flIwIUHJpb3JpdHmUk4..."`.

## Enabling JSON Serialization

To store JSON-serializable fields as readable values instead of pickled data, enable `prefer_normal_json_dump`. There are two ways to do this:

### Global Configuration

Enable for all models via `init_rapyer`:

```python
from rapyer import init_rapyer

await init_rapyer(
    redis="redis://localhost:6379/0",
    prefer_normal_json_dump=True
)
```

### Per-Model Configuration

Enable for a specific model via the `Meta` field:

```python
from enum import Enum
from rapyer import AtomicRedisModel
from rapyer.config import RedisConfig

class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class User(AtomicRedisModel):
    Meta = RedisConfig(prefer_normal_json_dump=True)

    name: str
    status: Status = Status.ACTIVE
```

With either configuration, the `status` field is stored as `"active"` in Redis - readable and inspectable.

## How It Works

When `prefer_normal_json_dump=True`:

1. Rapyer checks if each non-Redis field can be JSON serialized via Pydantic
2. Fields that pass this check are stored as plain JSON
3. Fields that can't be JSON serialized are still pickled

The check requires a default value to test serialization at model definition time.

## Supported Field Types

Fields that typically benefit from this setting:

- **Enums** - stored as their value
- **UUIDs** - stored as strings
- **Dates/times** - stored in ISO format
- **Named tuples** - stored as arrays

## Backward Compatibility

Rapyer automatically handles loading old pickled data for fields that are now JSON-serializable. No migration needed when enabling this feature on existing data.

## Requirements

For a field to use JSON serialization instead of pickle:

- The model must have `prefer_normal_json_dump=True`
- The field must have a default value (used to test serialization)
- The field type must be JSON serializable via Pydantic
