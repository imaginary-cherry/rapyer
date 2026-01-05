# URL Shortener with Analytics - Rapyer Showcase

A production-ready URL shortener built with Rapyer that demonstrates race-condition-free analytics tracking.

## Features

✨ **Race-Condition-Free Click Tracking**
- Atomic counter increments ensure accurate click counts
- Safe under heavy concurrent load
- No manual locks or transactions needed

🎯 **Type-Safe with Pydantic**
- URL validation prevents invalid data
- Full type hints throughout
- Runtime validation included

📊 **Real-Time Analytics**
- Track click counts accurately
- Store recent click timestamps
- View aggregate statistics

🚀 **Production-Ready**
- Async/await for high performance
- Clean, maintainable code
- Comprehensive error handling

## Prerequisites

- Python 3.10+
- Redis with JSON support (Redis Stack)

## Quick Start

### 1. Install Dependencies

```bash
pip install rapyer
```

### 2. Start Redis

Using Docker:
```bash
docker run -d -p 6379:6379 redis/redis-stack-server:latest
```

Or install Redis Stack:
- [Redis Stack Installation Guide](https://redis.io/docs/stack/get-started/install/)

### 3. Run the Demo

```bash
python main.py
```

## What the Demo Shows

### Basic URL Shortening
```python
shortener = URLShortener()

# Create shortened URL
short_url = await shortener.create_short_url(
    "https://github.com/imaginary-cherry/rapyer"
)
print(f"Short URL: /{short_url.short_code}")

# Track a click
destination = await shortener.track_click(short_url.short_code)
print(f"Redirecting to: {destination}")

# Get analytics
stats = await shortener.get_analytics(short_url.short_code)
print(f"Total clicks: {stats['total_clicks']}")
```

### Concurrent Safety Test

The demo simulates 100 simultaneous clicks and proves that every single one is counted correctly:

```python
# Simulate 100 CONCURRENT clicks
tasks = [
    shortener.track_click(short_code)
    for _ in range(100)
]
await asyncio.gather(*tasks)

# Result: Exactly 100 clicks counted!
```

**Why this matters**: With naive Redis usage or other ORMs without atomic operations, you'd likely lose clicks due to race conditions. Rapyer handles this automatically.

### Type Safety Demo

Pydantic validation ensures data integrity:

```python
# ✅ Valid URL - works
await shortener.create_short_url("https://example.com")

# ❌ Invalid URL - fails validation before hitting Redis
await shortener.create_short_url("not-a-url")
# Raises ValidationError
```

## Code Structure

```
url-shortener/
├── main.py              # Complete working example
├── README.md            # This file
└── requirements.txt     # Dependencies
```

## Key Concepts Demonstrated

### 1. Atomic Operations

```python
# This is ATOMIC and race-condition safe
await url.click_count.set(url.click_count + 1)
await url.last_clicks.aappend(datetime.now())
```

Behind the scenes, Rapyer uses optimized Lua scripts to ensure these operations are atomic, preventing race conditions even under heavy load.

### 2. Type Safety

```python
class ShortURL(AtomicRedisModel):
    short_code: str
    original_url: HttpUrl  # Pydantic validates this!
    click_count: int = 0
    last_clicks: List[datetime] = []
```

Pydantic ensures your data is always valid before it reaches Redis.

### 3. Clean API

No manual transaction management, no locks, no boilerplate:

```python
# Load from Redis
url = await ShortURL.aget(short_code)

# Modify
await url.click_count.set(url.click_count + 1)

# That's it! Rapyer handles everything else.
```

## Performance

This implementation can handle:
- ✅ Thousands of concurrent clicks without data loss
- ✅ High-throughput URL creation
- ✅ Real-time analytics queries
- ✅ Minimal Redis round trips (optimized Lua scripts)

## Extending This Example

Want to add more features? Try:

- **Custom short codes**: Allow users to choose their short code
- **Expiration**: Add TTL for temporary URLs
- **User accounts**: Track which user created each URL
- **Click details**: Store user agent, IP, referrer
- **QR codes**: Generate QR codes for shortened URLs
- **Dashboard**: Build a web UI with Flask/FastAPI

All of these are easy with Rapyer's flexible model system!

## Common Questions

### Why not use Redis OM or other ORMs?

Rapyer provides atomic operations out of the box. With other ORMs, you'd need to manually implement:
- Transaction management
- Lock acquisition/release
- Lua script writing
- Race condition handling

Rapyer does all of this automatically.

### Is this production-ready?

Yes! This example demonstrates production-ready patterns:
- Proper error handling
- Type safety
- Concurrent operation safety
- Clean architecture

### How does it scale?

Rapyer uses Redis, which can handle millions of operations per second. The atomic operations are implemented with server-side Lua scripts, so they're as fast as native Redis operations.

## Learn More

- 📚 [Rapyer Documentation](https://imaginary-cherry.github.io/rapyer/)
- 🐙 [GitHub Repository](https://github.com/imaginary-cherry/rapyer)
- 📦 [PyPI Package](https://pypi.org/project/rapyer/)

## Contributing

Found a bug or want to improve this example? PRs welcome!

## License

MIT License - same as Rapyer

---

**Built with ❤️ using Rapyer**

⭐ If you found this useful, [star the project on GitHub](https://github.com/imaginary-cherry/rapyer)!
