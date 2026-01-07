# Defining a Model

Creating models in Rapyer is straightforward and follows Pydantic conventions. Models automatically gain atomic Redis operations while maintaining full compatibility with standard Python types.

## Basic Model Definition

```python
from rapyer import AtomicRedisModel
from typing import List, Dict

class User(AtomicRedisModel):
    name: str
    age: int
    email: str
    balance: float = 0.0
    tags: List[str] = []
    preferences: Dict[str, str] = {}
```

## Redis Field Operations

Once defined, your model's fields support atomic Redis operations. Here's how to work with different field types:

```python
import asyncio

async def main():
    # Create a user instance
    user = User(
        name="Alice", 
        age=25, 
        email="alice@example.com",
        balance=100.50,
        tags=["python", "developer"],
        preferences={"theme": "dark", "language": "en"}
    )
    
    # Atomic list operations
    await user.tags.aappend("redis")           # Add single item
    await user.tags.aextend(["async", "web"])  # Add multiple items
    await user.tags.aremove("developer")       # Remove specific item
    
    # Atomic dictionary operations
    await user.preferences.aupdate(timezone="UTC")                    # Update/add key-value
    await user.preferences.aupdate({"theme": "light", "lang": "es"}) # Update multiple
    current_theme = await user.preferences.aget("theme")             # Get specific value
    await user.preferences.apop("language")                          # Remove and return value
    
    # Atomic string/numeric operations
    user.age += 1
    await user.age.asave()  # Save updated age atomically
    
    # Atomic float operations
    await user.balance.aincrease(50.25)  # Add to balance atomically
    
    print(f"Updated user: {user.name}, Age: {user.age}")
    print(f"Tags: {user.tags}")
    print(f"Current theme: {current_theme}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuring Redis Connection

Set Redis client and TTL directly on the model's Meta class:

```python
import redis.asyncio as redis
from rapyer import AtomicRedisModel

# Configure Redis client
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True  # IMPORTANT: Always set to True
)

class User(AtomicRedisModel):
    name: str
    age: int

# Configure after class definition
User.Meta.redis = redis_client
User.Meta.ttl = 3600  # Optional: 1 hour TTL
```

## Model Meta Configuration

The `Meta` class allows you to configure model-specific Redis settings:

```python
class User(AtomicRedisModel):
    name: str
    age: int
    
# Available Meta configurations
User.Meta.redis = redis_client    # Redis client instance
User.Meta.ttl = 3600             # Time-to-live in seconds (optional)
```

