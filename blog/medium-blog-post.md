# Building a Real-Time Game Leaderboard with Redis: A Race Condition Story

Imagine you need to build a leaderboard system for a multiplayer game. The requirements are straightforward: track player scores, show rankings, update in real-time. Redis seems like the perfect fit.

But within days of deployment, players start reporting issues. Scores don't add up. Achievements don't get awarded. Data gets corrupted. The culprit? Race conditions and the limitations of traditional Redis ORMs.

This is the story of how those challenges get solved with Rapyer.

## The Project: A Live Leaderboard

The requirements:
- Track player scores and update them atomically
- Store complex player data (stats, achievements, metadata)
- Update multiple fields together (score + achievements + rank)
- Handle player-to-player item transfers safely

Nothing unusual. But here's what happens.

## Attempt 1: Basic Redis

The first approach is simple:

```python
import redis.asyncio as redis
import json

async def add_score(player_id: str, points: int):
    r = await redis.Redis()

    # Get current score
    data = await r.get(f"player:{player_id}")
    player = json.loads(data)

    # Update score
    player['score'] += points

    # Save back
    await r.set(f"player:{player_id}", json.dumps(player))
```

This works in development. But in production, when two players earn points simultaneously, one update gets lost. Classic race condition.

## Attempt 2: Manual Locks

Adding locks fixes the immediate issue:

```python
async def add_score(player_id: str, points: int):
    lock = await r.lock(f"lock:player:{player_id}", timeout=10)

    if await lock.acquire():
        try:
            # Get, modify, save...
            pass
        finally:
            await lock.release()
```

This works for simple score updates. But then the requirements get more complex.

## The Real Challenge: Complex Player Data

Players aren't just scores. They have structured data:

```python
from dataclasses import dataclass
from enum import Enum

class Achievement(Enum):
    FIRST_WIN = "first_win"
    STREAK_10 = "streak_10"
    TOP_PLAYER = "top_player"

@dataclass
class PlayerStats:
    total_games: int
    wins: int
    avg_score: float
```

With Redis OM, you're forced to choose: `HashModel` (can't use dataclasses) or `JsonModel` (different API, manual transactions). Neither feels right.

With pydantic-redis, complex types need custom serialization, and transaction code is still manual.

## The Breaking Point: Multiple Operations Together

Here's where it breaks down completely.

When a player wins a game, several things need to happen:
1. Add points to their score
2. Increment their win count
3. Check and award achievements
4. Update their metadata

All of these need to happen **together**, atomically. If the server crashes halfway through, the data is corrupted.

With traditional ORMs, this means writing:

```python
async def player_wins(player_id: str, points: int):
    # Manually acquire lock
    lock = await redis.lock(f"lock:{player_id}", timeout=10)

    if await lock.acquire():
        try:
            async with redis.pipeline(transaction=True) as pipe:
                pipe.multi()
                # Manual Redis commands...
                pipe.hincrby(f"player:{player_id}", "score", points)
                pipe.hincrby(f"player:{player_id}", "wins", 1)
                # More manual commands...
                await pipe.execute()
        finally:
            await lock.release()
```

This is error-prone, hard to read, and you're basically writing raw Redis commands with JSON serialization glue.

## The Solution: Rapyer

Rapyer was built to solve exactly these problems. Here's the same leaderboard system with Rapyer:

```python
from rapyer import AtomicRedisModel, init_rapyer
from typing import List, Dict
from dataclasses import dataclass
from enum import Enum

class Achievement(Enum):
    FIRST_WIN = "first_win"
    STREAK_10 = "streak_10"
    TOP_PLAYER = "top_player"

@dataclass
class PlayerStats:
    total_games: int
    wins: int
    avg_score: float

class Player(AtomicRedisModel):
    username: str
    score: int = 0
    wins: int = 0
    achievements: List[Achievement] = []
    stats: PlayerStats = PlayerStats(0, 0, 0.0)
    metadata: Dict[str, str] = {}

# That's it. All types work. No HashModel vs JsonModel choice.
```

### Feature 1: Atomic Operations on Any Field

Every field gets atomic operations automatically:

```python
player = await Player.aget(player_id)

# Atomic score increment - no race conditions
await player.score.aincrease(100)

# Atomic list append - even with complex types
await player.achievements.aappend(Achievement.FIRST_WIN)

# Atomic dict update
await player.metadata.aupdate(last_win=datetime.now().isoformat())
```

No manual locks. No manual transactions. Each operation is atomic by default.

### Feature 2: Universal Type Support

Notice how `PlayerStats` is a dataclass and `Achievement` is an enum? They just work.

```python
# Update complex nested data
player.stats = PlayerStats(total_games=50, wins=30, avg_score=1250.5)
await player.asave()

# Load it back - everything works
loaded = await Player.aget(player_id)
print(loaded.stats.avg_score)  # 1250.5
print(loaded.achievements)  # [Achievement.FIRST_WIN]
```

With other ORMs, you're limited to their supported types or you write custom serialization. Rapyer handles any Python type automatically.

### Feature 3: Pipelines for Multiple Atomic Operations

Remember the "player wins" scenario? Here's how Rapyer handles it:

```python
async def player_wins(player_id: str, points: int):
    player = await Player.aget(player_id)

    async with player.apipeline() as p:
        # All operations execute as ONE atomic transaction
        p.score += points
        p.wins += 1
        await p.achievements.aappend(Achievement.STREAK_10)
        await p.metadata.aupdate(
            last_win=datetime.now().isoformat(),
            streak="10"
        )
        # Everything commits atomically on exit
```

All four operations happen together or not at all. No manual transaction management. No boilerplate.

### Feature 4: Locks for Complex Scenarios

For player-to-player item transfers, you need to lock both players:

```python
async def transfer_items(from_id: str, to_id: str, item_count: int):
    from_player = await Player.aget(from_id)
    to_player = await Player.aget(to_id)

    async with from_player.alock("transfer") as locked_from:
        if locked_from.inventory_count < item_count:
            raise ValueError("Not enough items")

        async with to_player.alock("transfer") as locked_to:
            locked_from.inventory_count -= item_count
            locked_to.inventory_count += item_count
            # Both saves happen atomically
```

Locks are built-in and work with context managers. No manual acquire/release.

## The Complete Leaderboard

Here's the full implementation:

```python
import asyncio
from rapyer import AtomicRedisModel, init_rapyer
from typing import List, Dict
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class Achievement(Enum):
    FIRST_WIN = "first_win"
    STREAK_10 = "streak_10"
    TOP_PLAYER = "top_player"

@dataclass
class PlayerStats:
    total_games: int
    wins: int
    losses: int
    avg_score: float

class Player(AtomicRedisModel):
    username: str
    score: int = 0
    wins: int = 0
    losses: int = 0
    achievements: List[Achievement] = []
    stats: PlayerStats = PlayerStats(0, 0, 0, 0.0)
    metadata: Dict[str, str] = {}

async def record_game_result(player_id: str, won: bool, points: int):
    """Record a game result - all updates are atomic"""
    player = await Player.aget(player_id)

    async with player.apipeline() as p:
        # Update score
        p.score += points if won else -points

        # Update win/loss record
        if won:
            p.wins += 1
        else:
            p.losses += 1

        # Award achievements
        if won and player.wins == 0:
            await p.achievements.aappend(Achievement.FIRST_WIN)

        if player.wins >= 10:
            await p.achievements.aappend(Achievement.STREAK_10)

        # Update metadata
        await p.metadata.aupdate(
            last_game=datetime.now().isoformat(),
            result="win" if won else "loss"
        )

async def get_leaderboard(limit: int = 10) -> List[Player]:
    """Get top players"""
    players = await Player.find()
    return sorted(players, key=lambda p: p.score, reverse=True)[:limit]

async def main():
    await init_rapyer(redis_url="redis://localhost:6379")

    # Create players
    player1 = Player(username="Alice")
    await player1.asave()

    player2 = Player(username="Bob")
    await player2.asave()

    # Record games
    await record_game_result(player1.pk, won=True, points=100)
    await record_game_result(player2.pk, won=True, points=150)

    # Get leaderboard
    top_players = await get_leaderboard(limit=5)
    for i, player in enumerate(top_players, 1):
        print(f"{i}. {player.username}: {player.score} points")

asyncio.run(main())
```

## What Makes Rapyer Different

**Works with any Python type**
Dataclasses, enums, nested objects - everything works. Other ORMs force you into their type system.

**Atomic by default**
Every field operation is atomic. No manual locks for simple operations.

**Pipeline for complex operations**
Multiple operations execute together atomically with clean syntax.

**Locks when you need them**
For complex scenarios like transfers, locks are built-in with context managers.

**One consistent API**
No choosing between HashModel and JsonModel. No different APIs for different types.

## Comparison

| Feature | Rapyer | Redis OM | pydantic-redis |
|---------|--------|----------|----------------|
| Any Python type | ✅ Yes | ❌ Limited | ❌ Limited |
| Field atomic operations | ✅ Built-in | ❌ Manual | ❌ Manual |
| Pipeline for multi-ops | ✅ Context manager | ⚠️ Manual | ❌ No |
| Lock management | ✅ Built-in | ❌ DIY | ❌ DIY |
| Pydantic v2 | ✅ Full | ✅ Yes | ⚠️ Limited |

## Try It

Install:
```bash
pip install rapyer
```

Redis with JSON support:
```bash
docker run -d -p 6379:6379 redis/redis-stack-server:latest
```

The complete leaderboard example is on GitHub in `examples/game-leaderboard/` (coming soon - for now see `examples/url-shortener/` for similar patterns).

## Documentation

Full docs: [imaginary-cherry.github.io/rapyer](https://imaginary-cherry.github.io/rapyer/)

## Summary

Building concurrent applications with Redis doesn't have to involve race conditions, manual locks, or type system limitations.

Rapyer provides:
- Atomic operations by default
- Support for any Python type
- Clean pipeline syntax for multi-operation atomicity
- Built-in lock management

If you're building with Redis and need data correctness, complex types, or atomic multi-field updates, Rapyer is worth checking out.

---

**Install**: `pip install rapyer`
**GitHub**: [github.com/imaginary-cherry/rapyer](https://github.com/imaginary-cherry/rapyer)
**Docs**: [imaginary-cherry.github.io/rapyer](https://imaginary-cherry.github.io/rapyer/)

⭐ Star it if you find it useful
