# Special Fields

Regular Redis types (`RedisStr`, `RedisList`, `RedisDict`, etc.) store their data **inline** within the model's JSON document. Special fields are different — they store data in a **separate Redis key** using a native Redis data structure.

This is useful for data that doesn't fit naturally into a JSON document, like sorted sets, streams, or other Redis-native structures.

## How They Differ from Regular Types

| | Regular Types | Special Fields |
|---|---|---|
| **Storage** | Inline in model JSON | Separate Redis key |
| **Redis structure** | JSON value | Native (sorted set, stream, etc.) |
| **Local state** | Yes — behaves like Python types | No — pure Redis proxy |
| **Auto-converted** | Yes (`list` → `RedisList`) | No — must be declared explicitly |
| **TTL** | Inherited from model | Automatically synced with model |

## Defining a Special Field

Special fields require an explicit type annotation and `Field(default_factory=...)`:

```python
from pydantic import Field
from rapyer import AtomicRedisModel
from rapyer.types import RedisPriorityQueue


class MyModel(AtomicRedisModel):
    name: str = "default"
    tasks: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue)
```
