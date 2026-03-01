<div align="center">
  <img src="icon.png" alt="Rapyer Logo" width="120">
  
  # Rapyer
  
  **Redis Atomic Pydantic Engine Reactor**
  
  *An async Redis ORM that provides atomic operations for complex data models*
  
  [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Redis](https://img.shields.io/badge/redis-6.0+-red.svg)](https://redis.io/)
  [![codecov](https://codecov.io/gh/imaginary-cherry/rapyer/branch/main/graph/badge.svg)](https://codecov.io/gh/imaginary-cherry/rapyer)
  [![PyPI version](https://badge.fury.io/py/rapyer.svg)](https://badge.fury.io/py/rapyer)
  [![Downloads](https://static.pepy.tech/badge/rapyer)](https://pepy.tech/project/rapyer)
  [![Documentation](https://img.shields.io/badge/docs-github.io-blue)](https://imaginary-cherry.github.io/rapyer/)

  
  📚 **[Full Documentation](https://imaginary-cherry.github.io/rapyer/)** | [Installation](https://imaginary-cherry.github.io/rapyer/installation/) | [Examples](https://imaginary-cherry.github.io/rapyer/examples/) | [API Reference](https://imaginary-cherry.github.io/rapyer/api/)
</div>

---

## What is Rapyer?

Rapyer (**R**edis **A**tomic **Py**dantic **E**ngine **R**eactor) is a modern async Redis ORM that enables atomic operations on complex data models. Built with Pydantic v2, it provides type-safe Redis interactions while maintaining data consistency and preventing race conditions.

### Key Features

🚀 **Atomic Operations** - Built-in atomic updates for complex Redis data structures  
⚡ **Async/Await** - Full asyncio support for high-performance applications  
🔒 **Type Safety** - Complete type validation using Pydantic v2  
🌐 **Universal Types** - Native optimization for primitives, automatic serialization for complex types  
🔄 **Race Condition Safe** - Lock context managers and pipeline operations  
📦 **Redis JSON** - Efficient storage using Redis JSON with support for nested structures

## Installation

```bash
pip install rapyer
```

**Requirements:**
- Python 3.10+
- Redis server with JSON module
- Pydantic v2

## Quick Start

```python
import asyncio
from rapyer.base import AtomicRedisModel
from typing import List, Dict


class User(AtomicRedisModel):
    name: str
    age: int
    tags: List[str] = []
    metadata: Dict[str, str] = {}


async def main():
    # Create and save a user
    user = User(name="John", age=30)
    await user.asave()

    # Atomic operations that prevent race conditions
    await user.tags.aappend("python")
    await user.tags.aextend(["redis", "pydantic"])
    await user.metadata.aupdate(role="developer", level="senior")

    # Load user from Redis
    loaded_user = await User.aget(user.key)
    print(f"User: {loaded_user.name}, Tags: {loaded_user.tags}")

    # Atomic operations with locks for complex updates
    async with user.alock("update_profile") as locked_user:
        locked_user.age += 1
        await locked_user.tags.aappend("experienced")
        # Changes saved atomically when context exits


if __name__ == "__main__":
    asyncio.run(main())
```

## Core Concepts

### Atomic Operations
Rapyer ensures data consistency with built-in atomic operations:

```python
# These operations are atomic and race-condition safe
await user.tags.aappend("python")           # Add to list
await user.metadata.aupdate(role="dev")     # Update dict
await user.score.set(100)                   # Set value
```

### Lock Context Manager
For complex multi-field updates:

```python
async with user.alock("transaction") as locked_user:
    locked_user.balance -= 50
    locked_user.transaction_count += 1
    # All changes saved atomically
```

### Pipeline Operations
Batch multiple operations for performance:

```python
async with user.apipeline() as pipelined_user:
    await pipelined_user.tags.aappend("redis")
    await pipelined_user.metadata.aupdate(level="senior")
    # Executed as single atomic transaction
```

## Type Support

Rapyer supports all Python types with automatic serialization:

- **Native types** (`str`, `int`, `List`, `Dict`) - Optimized Redis operations
- **Complex types** (`dataclass`, `Enum`, `Union`) - Automatic pickle serialization  
- **Nested models** - Full Redis functionality preserved

```python
from dataclasses import dataclass
from enum import Enum

@dataclass
class Config:
    debug: bool = False

class User(AtomicRedisModel):
    name: str = "default"
    scores: List[int] = []
    config: Config = Config()  # Auto-serialized
    
# All types work identically
user = User()
await user.config.set(Config(debug=True))  # Automatic serialization
await user.scores.aappend(95)               # Native Redis operation
```

## Why Choose Rapyer?

<!-- --8<-- [start:comparison] -->
### Comparison with Other Redis ORMs

| Feature | Rapyer                                          | Redis OM | pydantic-redis | orredis |
|---------|-------------------------------------------------|----------|----------------|---------|
| **🚀 Atomic Operations** | ✅ Built-in for all operations                   | ❌ Manual transactions only | ❌ Manual transactions only | ❌ Manual transactions only |
| **🔒 Lock Context Manager** | ✅ Automatic with `async with model.alock()`     | ❌ Manual implementation required | ❌ Manual implementation required | ❌ Manual implementation required |
| **⚡ Pipeline Operations** | ✅ True atomic batching with `model.apipeline()` | ⚠️ Basic pipeline support | ❌ No pipeline support | ❌ No pipeline support |
| **🌐 Universal Type Support** | ✅ Native + automatic serialization for any type | ⚠️ HashModel vs JsonModel limitations | ⚠️ Limited complex types | ⚠️ Limited complex types |
| **🔄 Race Condition Safe** | ✅ Built-in prevention with Lua scripts          | ❌ Manual implementation required | ❌ Manual implementation required | ❌ Manual implementation required |
| **📦 Redis JSON Native** | ✅ Optimized JSON operations                     | ✅ Via JsonModel only | ❌ Hash-based | ❌ Hash-based |
| **⚙️ Pydantic v2 Support** | ✅ Full compatibility                            | ✅ Recent support | ⚠️ Limited support | ⚠️ Basic support |
| **🎯 Type Safety** | ✅ Complete validation                           | ✅ Good validation | ✅ Good validation | ⚠️ Basic validation |
| **⚡ Performance** | ✅ Optimized operations                          | ✅ Good performance | ✅ Standard | ✅ Rust-optimized |
| **🔧 Nested Model Support** | ✅ Full Redis functionality preserved            | ⚠️ Limited nesting | ✅ Advanced relationships | ⚠️ Basic support |
| **🎛️ Custom Primary Keys** | ✅ Field annotations                             | ❌ ULIDs only | ✅ Custom fields | ✅ Custom fields |
| **🧪 Extensive Test Coverage** | ✅ 100%+ comprehensive tests with CI             | ⚠️ Basic testing with CI | ⚠️ Limited test coverage | ⚠️ Basic test suite |

<!-- --8<-- [end:comparison] -->

### 🏆 What Makes Rapyer Unique

#### **True Atomic Operations Out of the Box**

```python
# Rapyer - Atomic by default
await user.tags.aappend("python")  # Race-condition safe
await user.metadata.aupdate(role="dev")  # Always atomic

# Others - Manual transaction management required
async with redis.apipeline() as pipe:  # Manual setup
    pipe.multi()  # Manual transaction
    # ... manual Redis commands               # Error-prone
    await pipe.execute()
```

#### **Intelligent Lock Management**

```python
# Rapyer - Automatic lock context
async with user.alock("profile_update") as locked_user:
    locked_user.balance -= 50
    locked_user.transaction_count += 1
    # All changes saved atomically on exit

# Others - Manual lock implementation
lock_key = f"lock:{user.key}"
while not await redis.set(lock_key, token, nx=True):  # Manual retry logic
    await asyncio.sleep(0.1)  # Race conditions possible
# ... manual cleanup required
```

#### **Universal Type System**
```python
# Rapyer - Any Python type works identically
class User(AtomicRedisModel):
    scores: List[int] = []              # Native Redis operations
    config: MyDataClass = MyDataClass()  # Auto-serialized
    metadata: Dict[str, Any] = {}       # Native Redis operations

# All types support the same atomic operations
await user.config.set(new_config)      # Automatic serialization
await user.scores.aappend(95)           # Native Redis LIST operations
await user.metadata.aupdate(key="val") # Native Redis JSON operations
```

#### **Pipeline with True Atomicity**

```python
# Rapyer - Everything in pipeline is atomic
async with user.apipeline() as pipelined_user:
    await pipelined_user.tags.aappend("redis")
    await pipelined_user.metadata.aupdate(level="senior")
    # Single atomic transaction - either all succeed or all fail

# Others - No built-in pipeline abstraction for ORM operations
```

## Learn More

- 📖 **[Documentation](https://imaginary-cherry.github.io/rapyer/)** - Complete guide and API reference
- 🗺️ **[Roadmap](https://imaginary-cherry.github.io/rapyer/roadmap/)** - Future features and development plans

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
Thanks for [@Mizaro](https://github.com/Mizaro) and [@oazmiry](https://github.com/oazmiry) this would not have been possible without you. 

## License

MIT License