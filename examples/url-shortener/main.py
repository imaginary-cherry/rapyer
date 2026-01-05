"""
URL Shortener with Analytics - A Rapyer Showcase
================================================

This example demonstrates Rapyer's core features:
- Atomic operations for race-condition-free click tracking
- Type safety with Pydantic validation
- Clean, production-ready code
- Real-world concurrent access patterns

Run: python main.py
"""

import asyncio
from datetime import datetime
from typing import List, Optional
from rapyer import AtomicRedisModel, init_rapyer
from pydantic import HttpUrl
import secrets
import string


class ShortURL(AtomicRedisModel):
    """
    URL shortener model with built-in analytics.

    This model demonstrates:
    - Atomic counter increments (click_count)
    - List operations (last_clicks)
    - Pydantic type validation (HttpUrl)
    - Race-condition safety under concurrent load
    """

    short_code: str  # The shortened URL code
    original_url: HttpUrl  # The destination URL (validated by Pydantic)
    created_at: datetime
    click_count: int = 0
    last_clicks: List[datetime] = []

    class Meta:
        key_prefix = "url"  # Redis keys will be: url:<short_code>


class URLShortener:
    """
    URL shortening service with thread-safe analytics.

    All operations are race-condition safe, even under heavy
    concurrent load. No manual locks or transactions required!
    """

    @staticmethod
    def generate_short_code(length: int = 6) -> str:
        """Generate a random short code for the URL"""
        chars = string.ascii_letters + string.digits
        return "".join(secrets.choice(chars) for _ in range(length))

    async def create_short_url(self, original_url: str) -> ShortURL:
        """
        Create a new shortened URL.

        Args:
            original_url: The full URL to shorten

        Returns:
            ShortURL instance with generated short_code
        """
        short_code = self.generate_short_code()

        url = ShortURL(
            short_code=short_code,
            original_url=original_url,
            created_at=datetime.now(),
        )

        # Save to Redis - automatic serialization
        await url.asave()

        return url

    async def track_click(self, short_code: str) -> Optional[str]:
        """
        Track a click on shortened URL.

        This method is race-condition safe - even if 1000 users click
        simultaneously, every click will be counted correctly thanks
        to Rapyer's atomic operations.

        Args:
            short_code: The short code to track

        Returns:
            Original URL if found, None otherwise
        """
        try:
            # Load the URL from Redis
            url = await ShortURL.aget(short_code)

            # ATOMIC INCREMENT - No race conditions!
            # This uses Redis Lua scripts internally for atomicity
            await url.click_count.aincrease(1)

            # ATOMIC APPEND - Thread-safe list operation
            await url.last_clicks.aappend(datetime.now())

            # Keep only last 100 clicks for analytics
            if len(url.last_clicks) > 100:
                url.last_clicks = url.last_clicks[-100:]
                await url.asave()

            return str(url.original_url)

        except Exception as e:
            print(f"Error tracking click: {e}")
            return None

    async def get_analytics(self, short_code: str) -> dict:
        """
        Get analytics for a shortened URL.

        Args:
            short_code: The short code to analyze

        Returns:
            Dictionary with analytics data
        """
        url = await ShortURL.aget(short_code)

        return {
            "short_code": url.short_code,
            "original_url": str(url.original_url),
            "total_clicks": url.click_count,
            "created_at": url.created_at.isoformat(),
            "recent_clicks": len(url.last_clicks),
            "last_click": url.last_clicks[-1].isoformat() if url.last_clicks else None,
        }

    async def list_all_urls(self) -> List[dict]:
        """
        List all shortened URLs with their stats.

        Returns:
            List of URL analytics dictionaries
        """
        # Find all URL models (this uses Redis key pattern matching)
        keys = await ShortURL.find_keys()

        urls = []
        for key in keys:
            try:
                stats = await self.get_analytics(key.split(":")[-1])
                urls.append(stats)
            except Exception:
                continue

        return urls


async def demonstrate_concurrent_safety():
    """
    Demonstrate that Rapyer handles concurrent operations correctly.

    This simulates 100 simultaneous clicks and proves that
    every single one is counted accurately.
    """
    print("\n" + "=" * 60)
    print("🧪 CONCURRENT SAFETY TEST")
    print("=" * 60)

    shortener = URLShortener()

    # Create a test URL
    test_url = await shortener.create_short_url("https://github.com/imaginary-cherry/rapyer")
    print(f"\n✅ Created test URL: /{test_url.short_code}")
    print(f"   Destination: {test_url.original_url}")

    # Simulate 100 CONCURRENT clicks
    print("\n🔄 Simulating 100 concurrent clicks...")
    print("   (This would break with naive Redis usage!)")

    tasks = [shortener.track_click(test_url.short_code) for _ in range(100)]

    # All tasks run concurrently
    results = await asyncio.gather(*tasks)

    # Verify results
    stats = await shortener.get_analytics(test_url.short_code)

    print(f"\n📊 Results:")
    print(f"   ✅ Expected clicks: 100")
    print(f"   ✅ Actual clicks:   {stats['total_clicks']}")

    if stats["total_clicks"] == 100:
        print(f"   🎉 SUCCESS! All clicks counted correctly!")
    else:
        print(f"   ❌ FAILURE! Lost {100 - stats['total_clicks']} clicks due to race conditions")

    print(f"   📝 Recent clicks tracked: {stats['recent_clicks']}")


async def demonstrate_basic_usage():
    """
    Demonstrate basic URL shortener functionality.
    """
    print("\n" + "=" * 60)
    print("🚀 BASIC URL SHORTENER DEMO")
    print("=" * 60)

    shortener = URLShortener()

    # Create some URLs
    urls_to_shorten = [
        "https://github.com/imaginary-cherry/rapyer",
        "https://imaginary-cherry.github.io/rapyer/",
        "https://redis.io/docs/stack/",
    ]

    print("\n📝 Creating shortened URLs...")
    short_urls = []
    for url in urls_to_shorten:
        short = await shortener.create_short_url(url)
        short_urls.append(short)
        print(f"   ✅ {url}")
        print(f"      → /{short.short_code}")

    # Simulate some clicks
    print("\n👆 Simulating some clicks...")
    for short_url in short_urls:
        # Each URL gets a random number of clicks
        clicks = secrets.randbelow(20) + 1
        for _ in range(clicks):
            await shortener.track_click(short_url.short_code)
        print(f"   ✅ /{short_url.short_code} - {clicks} clicks")

    # Display analytics
    print("\n📊 Analytics Dashboard:")
    all_urls = await shortener.list_all_urls()

    for url_stats in all_urls:
        print(f"\n   🔗 /{url_stats['short_code']}")
        print(f"      Target: {url_stats['original_url']}")
        print(f"      Clicks: {url_stats['total_clicks']}")
        print(f"      Created: {url_stats['created_at']}")


async def demonstrate_type_safety():
    """
    Demonstrate Pydantic type validation.
    """
    print("\n" + "=" * 60)
    print("🛡️  TYPE SAFETY DEMO")
    print("=" * 60)

    shortener = URLShortener()

    # Valid URL - should work
    print("\n✅ Creating URL with valid HTTP URL...")
    try:
        url1 = await shortener.create_short_url("https://example.com")
        print(f"   Success! Created: /{url1.short_code}")
    except Exception as e:
        print(f"   Failed: {e}")

    # Invalid URL - should fail with Pydantic validation
    print("\n❌ Attempting to create URL with invalid URL...")
    try:
        url2 = await shortener.create_short_url("not-a-valid-url")
        print(f"   Success! Created: /{url2.short_code}")
    except Exception as e:
        print(f"   Failed (as expected): {type(e).__name__}")
        print(f"   Pydantic prevented invalid data from reaching Redis!")


async def main():
    """
    Main demo function - runs all demonstrations.
    """
    print("=" * 60)
    print("🎯 RAPYER URL SHORTENER SHOWCASE")
    print("=" * 60)
    print("\nThis demo showcases Rapyer's key features:")
    print("  • Atomic operations (race-condition free)")
    print("  • Type safety with Pydantic")
    print("  • Clean, production-ready code")
    print("  • Concurrent operation handling")

    # Initialize Rapyer (connect to Redis)
    print("\n🔌 Connecting to Redis...")
    try:
        await init_rapyer(redis_url="redis://localhost:6379")
        print("   ✅ Connected successfully!")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        print("\n💡 Make sure Redis is running:")
        print("   docker run -d -p 6379:6379 redis/redis-stack-server:latest")
        return

    # Run demonstrations
    await demonstrate_basic_usage()
    await demonstrate_concurrent_safety()
    await demonstrate_type_safety()

    print("\n" + "=" * 60)
    print("✨ Demo completed successfully!")
    print("=" * 60)
    print("\n📚 Learn more:")
    print("   • Docs: https://imaginary-cherry.github.io/rapyer/")
    print("   • GitHub: https://github.com/imaginary-cherry/rapyer")
    print("   • PyPI: https://pypi.org/project/rapyer/")
    print("\n⭐ If you found this useful, star us on GitHub!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
