# Why I Built Rapyer: A Redis ORM That Doesn't Hate You

I've been working with Redis in Python for years, and I kept running into the same annoying problem: **race conditions**.

You know the drill. You build something with Redis. Works great on your laptop. Deploy it. Suddenly users are seeing weird bugs because two requests modified the same data at the exact same time. Now you're Googling "redis lua scripts" at 2am trying to figure out how to make a simple counter increment atomically.

There had to be a better way.

## The Problem

Let's say you're building a URL shortener (classic example, I know). You want to track clicks. Simple, right?

```python
# Seems fine...
url_data = await redis.get(f"url:{code}")
clicks = url_data['clicks']
clicks += 1
url_data['clicks'] = clicks
await redis.set(f"url:{code}", url_data)
```

**Plot twist**: If two people click at the same time, you just lost a click. Both read `clicks=5`, both write `clicks=6`. One click vanished into the void.

The "correct" solution? Manual locks, transactions, Lua scripts, and a bunch of boilerplate that makes you question your life choices.

## What I Wanted

I wanted to write this instead:

```python
url = await ShortURL.aget(code)
await url.clicks.set(url.clicks + 1)
```

And have it **just work**. No locks. No transactions. No Lua. Just atomic by default.

So I built Rapyer.

## What is Rapyer?

Rapyer (Redis Atomic Pydantic Engine Reactor) is a Redis ORM that treats concurrency as a first-class feature, not an afterthought.

It's built on Pydantic v2, so you get full type safety. It uses async/await. And most importantly: **operations are atomic by default**.

Here's a real example:

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

# These are ATOMIC - no race conditions!
await user.score.set(user.score + 10)
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
    """Track a click - RACE CONDITION SAFE!"""
    url = await ShortURL.aget(code)

    # Both of these are atomic
    await url.clicks.set(url.clicks + 1)
    await url.recent_clicks.aappend(datetime.now())

    return str(url.original_url)

async def main():
    await init_rapyer(redis_url="redis://localhost:6379")

    # Create a short URL
    short = await create_short_url("https://github.com/imaginary-cherry/rapyer")
    print(f"Created: /{short.short_code}")

    # Simulate 100 CONCURRENT clicks
    await asyncio.gather(*[
        track_click(short.short_code)
        for _ in range(100)
    ])

    # Check the count
    url = await ShortURL.aget(short.short_code)
    print(f"Clicks: {url.clicks}")  # Will be exactly 100!

asyncio.run(main())
```

Run this. You'll get exactly 100 clicks counted, even though they all happened concurrently. That's the magic of atomic operations.

## How It Works (The Interesting Parts)

### Atomic Operations

Under the hood, Rapyer uses Lua scripts for atomic operations. But you never see them:

```python
# This becomes a Lua script that runs atomically on Redis
await user.score.set(user.score + 10)

# So does this
await user.tags.aappend("new-tag")

# And this
await user.metadata.aupdate(status="active", level=5)
```

### Lock Context Manager

For complex multi-field updates, there's a lock context:

```python
async with user.alock("profile_update") as locked_user:
    locked_user.score += 100
    locked_user.level = "pro"
    locked_user.updated_at = datetime.now()
    # Everything saves atomically when the context exits
```

### Pipeline Operations

Need to batch operations? There's a pipeline context:

```python
async with user.apipeline() as p:
    await p.score.set(100)
    await p.tags.aappend("verified")
    await p.metadata.aupdate(status="active")
    # Executes as one atomic transaction
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
    preferences: Preferences = Preferences("dark", True)  # Auto-serialized
    role: Role = Role.USER  # Enums work
    scores: List[int] = []  # Native Redis operations
```

## Why Not Use [Other ORM]?

**Redis OM**: Great library! But you have to choose between `HashModel` (limited types) and `JsonModel` (different API). And atomic operations? You're on your own.

**pydantic-redis**: Solid Pydantic integration, but it's basically a wrapper around redis-py. You're still writing manual transaction code.

**Rapyer**: Atomic by default. Any type works. One consistent API. That's it.

## Quick Comparison

| Thing You Want | Rapyer | Others |
|----------------|--------|--------|
| Atomic operations | ✅ Built-in | ❌ DIY |
| Lock management | ✅ Context manager | ❌ Manual |
| Any Python type | ✅ Yes | ⚠️ Depends |
| Race condition safe | ✅ By default | ❌ Your problem |
| Pydantic v2 | ✅ Full support | ⚠️ Varies |

## Real-World Use Cases

**E-commerce**: Prevent overselling with atomic inventory decrements

**Analytics**: Track clicks/views accurately under heavy load

**Gaming**: Update player scores and leaderboards without race conditions

**Caching**: Store complex objects with automatic serialization

**Rate Limiting**: Atomic counters for API throttling

**Session Management**: Store user sessions with type safety

## Getting Started (60 seconds)

Install:
```bash
pip install rapyer
```

You need Redis with JSON support. Use Redis Stack:
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
    await counter.value.set(counter.value + 1)

    print(f"Counter: {counter.value}")

asyncio.run(main())
```

That's it. You're up and running.

## Performance

It's fast. Rapyer uses:
- Native Redis JSON operations
- Server-side Lua scripts (minimal network overhead)
- Connection pooling
- Async I/O throughout

In practice, it handles thousands of concurrent operations without breaking a sweat. The URL shortener example? We've tested it with 10,000 concurrent clicks. All counted correctly.

## What I Learned Building This

**1. Concurrency is hard**
Race conditions are subtle. They don't show up in tests. They appear in production at 3am.

**2. Abstractions matter**
Hiding Lua scripts behind a clean API makes a huge difference in developer experience.

**3. Type safety is worth it**
Catching errors before they hit Redis saves debugging time.

**4. Atomic by default is the right choice**
You shouldn't have to opt-in to correctness.

## Try It

The full URL shortener example is on GitHub in the `examples/` directory. Clone it, run it, break it. See how it handles concurrent load.

```bash
git clone https://github.com/imaginary-cherry/rapyer
cd rapyer/examples/url-shortener
pip install rapyer
python main.py
```

## Documentation

Full docs are at [imaginary-cherry.github.io/rapyer](https://imaginary-cherry.github.io/rapyer/)

Topics covered:
- Installation and setup
- Model creation and fields
- Atomic operations guide
- Lock and pipeline patterns
- Type system deep dive
- API reference

## Contributing

Found a bug? Want a feature? PRs welcome!

GitHub: [github.com/imaginary-cherry/rapyer](https://github.com/imaginary-cherry/rapyer)

## Final Thoughts

I built Rapyer because I was tired of fighting Redis race conditions. I wanted to write clean code and have it just work.

If you've ever:
- Lost data to race conditions
- Written manual Redis locks
- Debugged weird concurrency bugs
- Wished Redis ORMs "just handled this"

Give Rapyer a try.

It might save you a few 2am debugging sessions.

---

**Install**: `pip install rapyer`
**Docs**: [imaginary-cherry.github.io/rapyer](https://imaginary-cherry.github.io/rapyer/)
**GitHub**: [github.com/imaginary-cherry/rapyer](https://github.com/imaginary-cherry/rapyer)

⭐ Star it if you find it useful!

---

*Questions? Comments? Drop them below or open an issue on GitHub. Happy to help!*
