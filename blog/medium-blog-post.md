# Why I Built Rapyer: A Redis ORM That Handles Concurrency

I've been working with Redis in Python for a few years, and I kept running into the same problem: **race conditions**.

You know the situation. You build something with Redis. Works fine on your laptop. Deploy it. Then you notice bugs because two requests modified the same data simultaneously. Now you're looking up Lua scripts trying to figure out how to make a counter increment atomically.

There had to be a better way.

## The Problem

Let's say you're building a URL shortener. You want to track clicks. Seems straightforward:

```python
# Looks fine...
url_data = await redis.get(f"url:{code}")
clicks = url_data['clicks']
clicks += 1
url_data['clicks'] = clicks
await redis.set(f"url:{code}", url_data)
```

But if two people click at the same time, you lose a click. Both read `clicks=5`, both write `clicks=6`. One click disappears.

The usual solution involves manual locks, transactions, Lua scripts, and boilerplate that makes simple operations complicated.

## What I Wanted

I wanted to write this instead:

```python
url = await ShortURL.aget(code)
await url.clicks.aincrease(1)
```

And have it just work. No locks. No transactions. No Lua. Atomic by default.

So I built Rapyer.

## What is Rapyer?

Rapyer (Redis Atomic Pydantic Engine Reactor) is a Redis ORM that treats concurrency as a first-class feature.

It's built on Pydantic v2 for type safety. It uses async/await. And operations are atomic by default.

Here's a basic example:

```python
from rapyer import AtomicRedisModel
from typing import List

class User(AtomicRedisModel):
    name: str
    score: int = 0
    tags: List[str] = []

# Create and save
user = User(name="Alice", score=100)
await user.asave()

# These are ATOMIC - no race conditions
await user.score.aincrease(10)
await user.tags.aappend("winner")

# Load from Redis
loaded = await User.aget(user.key)
print(f"{loaded.name}: {loaded.score} points")
```

No locks. No transactions. It just works.

## Show Me Something Real

Okay, let's build that URL shortener properly. Here's the whole thing:

```python
import asyncio
from datetime import datetime
from typing import List
from rapyer import AtomicRedisModel, init_rapyer
from pydantic import HttpUrl
import secrets
import string

class ShortURL(AtomicRedisModel):
    short_code: str
    original_url: HttpUrl  # Pydantic validates URLs!
    created_at: datetime
    clicks: int = 0
    recent_clicks: List[datetime] = []

async def create_short_url(long_url: str) -> ShortURL:
    """Create a shortened URL"""
    code = ''.join(secrets.choice(string.ascii_letters) for _ in range(6))

    url = ShortURL(
        short_code=code,
        original_url=long_url,
        created_at=datetime.now()
    )
    await url.asave()
    return url

async def track_click(code: str) -> str:
    """Track a click - race condition safe"""
    url = await ShortURL.aget(code)

    # Both operations are atomic
    await url.clicks.aincrease(1)
    await url.recent_clicks.aappend(datetime.now())

    return str(url.original_url)

async def main():
    await init_rapyer(redis_url="redis://localhost:6379")

    # Create a short URL
    short = await create_short_url("https://github.com/imaginary-cherry/rapyer")
    print(f"Created: /{short.short_code}")

    # Simulate 100 concurrent clicks
    await asyncio.gather(*[
        track_click(short.short_code)
        for _ in range(100)
    ])

    # Check the count
    url = await ShortURL.aget(short.short_code)
    print(f"Clicks: {url.clicks}")  # Exactly 100

asyncio.run(main())
```

Run this and you'll get exactly 100 clicks counted, even with concurrent execution.

## How It Works

### Atomic Operations

Rapyer uses Lua scripts for atomic operations, but you don't see them:

```python
# Atomic increment
await user.score.aincrease(10)

# Atomic list append
await user.tags.aappend("new-tag")

# Atomic dict update
await user.metadata.aupdate(status="active", level=5)
```

### Lock Context Manager

For complex multi-field updates:

```python
async with user.alock("profile_update") as locked_user:
    locked_user.score += 100
    locked_user.level = "pro"
    locked_user.updated_at = datetime.now()
    # Saves atomically on exit
```

### Pipeline Operations

For batching operations:

```python
async with user.apipeline() as p:
    p.score += 100
    await p.tags.aappend("verified")
    await p.metadata.aupdate(status="active")
    # Executes as one transaction
```

### Universal Type Support

Any Python type just works:

```python
from dataclasses import dataclass
from enum import Enum

@dataclass
class Preferences:
    theme: str
    notifications: bool

class Role(Enum):
    USER = "user"
    ADMIN = "admin"

class User(AtomicRedisModel):
    name: str
    preferences: Preferences = Preferences("dark", True)
    role: Role = Role.USER
    scores: List[int] = []
```

## Why Not Use Other ORMs?

**Redis OM**: Good library, but you choose between `HashModel` (limited types) and `JsonModel` (different API). Atomic operations are manual.

**pydantic-redis**: Solid Pydantic integration, but it's a thin wrapper around redis-py. You still write transaction code manually.

**Rapyer**: Atomic by default. Any type works. One consistent API.

## Quick Comparison

| Feature | Rapyer | Others |
|---------|--------|--------|
| Atomic operations | ✅ Built-in | ❌ Manual |
| Lock management | ✅ Context manager | ❌ DIY |
| Any Python type | ✅ Yes | ⚠️ Depends |
| Race condition safe | ✅ By default | ❌ Your responsibility |
| Pydantic v2 | ✅ Full support | ⚠️ Varies |

## Real-World Use Cases

**E-commerce**: Atomic inventory decrements prevent overselling

**Analytics**: Accurate click/view tracking under load

**Gaming**: Score updates and leaderboards without race conditions

**Caching**: Store complex objects with automatic serialization

**Rate Limiting**: Atomic counters for API throttling

**Sessions**: Store user sessions with type safety

## Getting Started

Install:
```bash
pip install rapyer
```

You need Redis with JSON support (Redis Stack):
```bash
docker run -d -p 6379:6379 redis/redis-stack-server:latest
```

Hello World:
```python
import asyncio
from rapyer import AtomicRedisModel, init_rapyer

class Counter(AtomicRedisModel):
    value: int = 0

async def main():
    await init_rapyer(redis_url="redis://localhost:6379")

    counter = Counter()
    await counter.asave()

    # Atomic increment
    await counter.value.aincrease(1)

    print(f"Counter: {counter.value}")

asyncio.run(main())
```

## Performance

Rapyer uses:
- Native Redis JSON operations
- Server-side Lua scripts (minimal network overhead)
- Connection pooling
- Async I/O throughout

It handles thousands of concurrent operations without issues. The URL shortener example works correctly with 10,000 concurrent clicks.

## What I Learned

**Concurrency is subtle**
Race conditions don't show up in tests. They appear in production.

**Abstractions matter**
Hiding Lua scripts behind a clean API improves developer experience significantly.

**Type safety helps**
Catching errors before they hit Redis saves debugging time.

**Atomic by default is right**
You shouldn't have to opt-in to correctness.

## Try It

The full URL shortener example is on GitHub in `examples/url-shortener/`:

```bash
git clone https://github.com/imaginary-cherry/rapyer
cd rapyer/examples/url-shortener
pip install rapyer
python main.py
```

## Documentation

Full docs at [imaginary-cherry.github.io/rapyer](https://imaginary-cherry.github.io/rapyer/)

Topics:
- Installation and setup
- Model creation and fields
- Atomic operations guide
- Lock and pipeline patterns
- Type system details
- API reference

## Contributing

Found a bug? Want a feature? PRs welcome at [github.com/imaginary-cherry/rapyer](https://github.com/imaginary-cherry/rapyer)

## Final Thoughts

I built Rapyer because I was tired of fighting Redis race conditions. I wanted clean code that just works.

If you've dealt with:
- Data loss from race conditions
- Manual Redis locks
- Concurrency bugs
- ORMs that don't handle this

Give Rapyer a try.

---

**Install**: `pip install rapyer`
**Docs**: [imaginary-cherry.github.io/rapyer](https://imaginary-cherry.github.io/rapyer/)
**GitHub**: [github.com/imaginary-cherry/rapyer](https://github.com/imaginary-cherry/rapyer)

⭐ Star it if you find it useful

---

*Questions? Drop them below or open an issue on GitHub.*
