# Overview

<div align="center" markdown="1">

<img src="icon.png" alt="Rapyer Logo" width="120" style="margin-bottom: 2rem;">

**Pydantic models with Redis as the storage backend**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Redis](https://img.shields.io/badge/redis-6.0+-red.svg)](https://redis.io/)
[![codecov](https://codecov.io/gh/imaginary-cherry/rapyer/branch/main/graph/badge.svg)](https://codecov.io/gh/imaginary-cherry/rapyer)
[![CodSpeed Badge](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://codspeed.io/imaginary-cherry/rapyer?utm_source=badge)
[![PyPI version](https://badge.fury.io/py/rapyer.svg)](https://badge.fury.io/py/rapyer)
[![Downloads](https://static.pepy.tech/badge/rapyer)](https://pepy.tech/project/rapyer)
[![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)](https://redis.io)

</div>

## 🚀 Why Redis?

Redis is an in-memory key-value store designed for fast caching, queues, and real-time data processing. It offers high speed, atomic operations, and excellent scalability, making it ideal for low-latency applications. 

!!! info "Performance Benefits"
    Redis provides **microsecond-level latency** and can handle millions of operations per second, making it perfect for real-time applications.

## ⚡ The Power of Pydantic

Pydantic has revolutionized Python data validation and serialization. There are already many libraries that use Pydantic for ORM: Beanie (MongoDB), FastAPI (HTTP server), etc. However, the current packages to support Redis are somewhat lacking.

!!! tip "Type Safety"
    Pydantic's strength lies in its **automatic validation**, **type safety**, and **developer-friendly API** that makes working with complex data structures intuitive and safe.

## 🎯 Introducing Rapyer

Rapyer bridges the gap between Redis's performance and Pydantic's type safety, creating a powerful combination optimized for real-world applications.

### 🔧 Wide Variety of Field Support

Rapyer supports a wide variety of field types and offers users the ability to perform complex atomic actions on these fields:

=== "Primitive Types"
    - **Strings** - Optimized Redis string storage
    - **Integers** - Native Redis number handling  
    - **Floats** - Precise decimal operations
    - **Booleans** - Efficient boolean storage

=== "Collection Types"
    - **Lists** - Full atomic list operations
    - **Dictionaries** - Atomic dict updates and lookups
    - **Sets** - Redis set operations with Python interface

=== "Specialized Types"
    - **RedisStr** - Enhanced string type with IDE autocomplete
    - **RedisList** - List type with atomic operations
    - **RedisDict** - Dictionary type with atomic operations

!!! note "Custom Types"
    You can also create your own custom types or decide how to save the data in Redis. Other types are also supported - essentially we support any type that can be serialized to pickle, however, they can be used to perform atomic operations.

### ⚛️ Atomic Operations for Race Condition Prevention

Every operation in Rapyer is designed to be atomic and safe in concurrent environments:

```python title="Atomic Operations Example"
# All operations are atomic - no race conditions possible
await user.tags.aappend("python")          # Atomic list append
await user.metadata.aupdate(role="dev")    # Atomic dict update
user.score += 10
await user.score.asave()                   # Atomic increment
```

!!! success "Concurrency Safe"
    For complex multi-field operations, Rapyer provides **lock context managers** and **pipeline operations** that ensure consistency across multiple changes.

## 🚀 Quick Example

```python title="Complete Rapyer Example"
import asyncio
from rapyer import AtomicRedisModel
from typing import List, Dict


class User(AtomicRedisModel):
    name: str
    age: int
    tags: List[str] = []
    metadata: Dict[str, str] = {}


async def main():
    # Create and save
    user = User(name="Alice", age=25)
    await user.asave()

    # Atomic operations
    await user.tags.aappend("developer")                    # (1)!
    await user.tags.aextend(["python", "redis"])           # (2)!
    await user.metadata.aupdate(team="backend", level="senior")  # (3)!

    # Load and verify
    loaded = await User.aget(user.key)
    print(f"User: {loaded.name}, Tags: {loaded.tags}")     # (4)!


if __name__ == "__main__":
    asyncio.run(main())
```

1. Add a single tag atomically
2. Extend with multiple tags in one operation  
3. Update multiple metadata fields atomically
4. Load the complete model from Redis

!!! abstract "Core Philosophy"
    This example demonstrates Rapyer's core philosophy: combine **Redis performance** with **Pydantic safety**, all while maintaining **atomic operations** that prevent data corruption in concurrent applications.

## Why Choose Rapyer?

--8<-- "README.md:comparison"
