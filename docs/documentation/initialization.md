# Initialization

Rapyer provides global initialization functions to configure all your models at once, making it easy to manage Redis connections and settings across your entire application.

## init_rapyer Function

The `init_rapyer` function allows you to configure Redis clients and TTL settings for all AtomicRedisModel classes in your application simultaneously.

### Basic Usage

```python
import redis.asyncio as redis
from rapyer import AtomicRedisModel, init_rapyer

# Define your models first
class User(AtomicRedisModel):
    name: str
    age: int

class Session(AtomicRedisModel):
    user_id: str
    data: dict = {}

class Product(AtomicRedisModel):
    name: str
    price: float

# Initialize all models with Redis client
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True
)

# This sets Redis client for ALL AtomicRedisModel classes
await init_rapyer(redis=redis_client)
```

### Using Redis URL

```python
# Initialize with Redis URL string
await init_rapyer(redis="redis://localhost:6379/0")

# For production with authentication
await init_rapyer(redis="redis://username:password@redis-server:6379/0")

# Redis Cluster
await init_rapyer(redis="redis://cluster-endpoint:6379/0")
```

### Setting Global TTL

```python
# Set TTL for all models (1 hour)
await init_rapyer(redis=redis_client, ttl=3600)

# TTL only (if Redis already configured)
await init_rapyer(ttl=1800)  # 30 minutes
```

### Advanced Configuration

```python
# Custom connection pool with init_rapyer
redis_client = redis.Redis.from_url(
    "redis://localhost:6379/0",
    max_connections=20,
    decode_responses=True
)

await init_rapyer(redis=redis_client, ttl=3600)
```

## Special Field Initialization

**Important:** `init_rapyer` is crucial for initializing special fields like indexed fields and other advanced features.
For simple usage, it is possible to simply set the redis client yourself.

!!! warning "`RedisText` requires real Redis"
    `RedisText` fields are **not supported under `fakeredis`** and this is not
    checked at `init_rapyer()`. The embedding is written as raw `FLOAT32` bytes
    into a HASH, and the `aget_or_create` path decodes it inside a Lua script —
    neither round-trips faithfully on `fakeredis`. Use a real Redis instance for
    any model carrying a `RedisText` field.

## Generic Models

!!! warning "Generic origin models are skipped during initialization"
    A **generic origin** — declared as
    `class MyModel(AtomicRedisModel, Generic[T])` with unbound type
    parameters — is automatically left out of `init_rapyer`. Register and use a
    concrete parametrization instead:

    <!-- markdownlint-disable-next-line MD046 -->
    ```python
    T = TypeVar("T")

    class Event(AtomicRedisModel, Generic[T]):  # origin: auto-skipped
        payload: T

    class StrEvent(Event[str]):
        ...  # concrete subclass — registered, initialized, queryable
    ```

??? note "Why generic origins are skipped (mechanics)"
    The query API exposes each field as a class attribute (so `User.age > 18`
    works), and `init_rapyer` installs those attributes. Pydantic treats a
    class attribute that matches a field name as that field's **default**, so on
    a generic origin the installed attribute would shadow the real default —
    and any concrete parametrization (`MyModel[str]`) built *afterwards* would
    inherit that shadowed default and fail to construct. Rapyer avoids this by
    not registering origins with unbound type parameters; their concrete
    parametrizations are registered normally.

## teardown_rapyer Function

The `teardown_rapyer` function properly closes Redis connections for all models, ensuring clean resource cleanup.

### Basic Cleanup

```python
from rapyer import teardown_rapyer

async def cleanup():
    # Closes Redis connections for all models
    await teardown_rapyer()
```

### Application Lifecycle

```python
import asyncio
from rapyer import init_rapyer, teardown_rapyer, AtomicRedisModel


class User(AtomicRedisModel):
    name: str
    age: int


async def main():
    try:
        # Initialize at application startup
        await init_rapyer(redis="redis://localhost:6379/0")

        # Your application logic
        user = User(name="Alice", age=25)
        await user.asave()

        # Application operations...

    finally:
        # Always cleanup at application shutdown
        await teardown_rapyer()


if __name__ == "__main__":
    asyncio.run(main())
```

### FastAPI Integration

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from rapyer import init_rapyer, teardown_rapyer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_rapyer(redis="redis://localhost:6379/0")
    yield
    # Shutdown
    await teardown_rapyer()

app = FastAPI(lifespan=lifespan)
```

## Configuration Patterns

### Environment-Based Initialization

```python
import os
from rapyer import init_rapyer

async def setup_redis():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    ttl = int(os.getenv("REDIS_TTL", "3600"))  # Default 1 hour
    
    await init_rapyer(redis=redis_url, ttl=ttl)
```

### Conditional Configuration

```python
async def initialize_models():
    if os.getenv("ENV") == "production":
        # Production Redis with TTL
        await init_rapyer(
            redis="redis://prod-redis:6379/0",
            ttl=7200  # 2 hours
        )
    elif os.getenv("ENV") == "testing":
        # Test Redis without TTL
        await init_rapyer(redis="redis://test-redis:6379/1")
    else:
        # Local development
        await init_rapyer(redis="redis://localhost:6379/0")
```

## Benefits of Global Initialization

### 1. Centralized Configuration
- **Single point** of Redis configuration for all models
- **Consistent settings** across your entire application
- **Environment-based** configuration made simple

### 2. Special Field Support
- **Indexed fields** and other advanced features require proper initialization
- **Global setup** ensures all special fields work correctly
- **Feature activation** happens automatically

### 3. Resource Management
- **Proper cleanup** with teardown_rapyer
- **Connection pooling** configured once for all models
- **Memory efficiency** through shared Redis connections

### 4. Development Workflow
- **Easy testing** - initialize once for all test models
- **Configuration switching** between environments
- **Simplified deployment** with environment variables

## Best Practices

### 1. Initialize Early
```python
# ✓ Initialize before using any models
await init_rapyer(redis="redis://localhost:6379/0")
user = User(name="Alice")  # Now ready to use

# ✗ Don't use models before initialization
user = User(name="Alice")  # May not work correctly
await init_rapyer(redis="redis://localhost:6379/0")
```

### 2. Always Use teardown_rapyer
```python
try:
    await init_rapyer(redis="redis://localhost:6379/0")
    # Application logic
finally:
    await teardown_rapyer()  # Always cleanup
```

### 3. Handle Multiple Redis Instances
```python
# For models that need different Redis instances
await init_rapyer(redis="redis://localhost:6379/0")  # Default for most models

# Override specific models if needed
SpecialModel.Meta.redis = redis.from_url("redis://special-redis:6379/0")
```

Global initialization makes managing Redis connections across your application simple, reliable, and efficient!