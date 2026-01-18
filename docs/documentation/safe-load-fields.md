# Safe Loading Fields

Safe loading is a flag that you can use when non-redis resource cant be load from anywhere.
If a field must have specific resources to load it, but you still want to use the models, for example, storing type that is stored in a specific service (not every can use it in you infrastructure).

### Basic Usage

```python
from typing import Optional
from rapyer import AtomicRedisModel
from rapyer.fields import SafeLoad

class Plugin(AtomicRedisModel):
    handler_class: SafeLoad[Optional[type]] = None
    name: str
```

### Model-Wide Configuration

For models with many such fields, enable it globally:

```python
from rapyer import AtomicRedisModel
from rapyer.config import RedisConfig

class DynamicConfig(AtomicRedisModel):
    Meta = RedisConfig(safe_load_all=True)

    type_field: Optional[type] = None  # Automatically safe
    name: str = "default"  # Not affected (already serializable)
```

### Checking What Failed

After loading, check which fields couldn't be restored:

```python
plugin = await Plugin.aget("plugin-123")

if plugin.failed_fields:
    print(f"Could not load: {plugin.failed_fields}")
    # Use a fallback
    plugin.handler_class = DefaultHandler
```

### Example: Plugin System

```python
class Plugin(AtomicRedisModel):
    handler: SafeLoad[Optional[type]] = None
    name: str

async def load_plugin(plugin_id: str):
    plugin = await Plugin.aget(plugin_id)

    if "handler" in plugin.failed_fields:
        return DefaultHandler()

    return plugin.handler() if plugin.handler else DefaultHandler()
```

## Things to Know

- **Always use `Optional`** - the field can become `None` if loading fails
- **Check `failed_fields`** - know when something went wrong
- **Warnings are logged** - configure `logging.getLogger("rapyer")` to see them

## Behavior Differences

Safe loading behaves differently depending on the field type:

- **Model fields** - when a field cannot be deserialized, it is set to `None` and tracked in `failed_fields`
- **Collection fields (`RedisList`, `RedisDict`)** - items that cannot be deserialized are **skipped entirely** (not included in the result)
