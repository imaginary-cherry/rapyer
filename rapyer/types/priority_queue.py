import logging
from dataclasses import dataclass
from typing import TypeVar, Generic, Any, Iterator, TYPE_CHECKING

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from pydantic_core.core_schema import CoreSchema

from rapyer.context import _context_var
from rapyer.utils.redis import refresh_ttl_if_needed

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel
    from rapyer.types.base import RedisType

logger = logging.getLogger("rapyer")

T = TypeVar("T")


@dataclass
class PriorityItem(Generic[T]):
    """Represents an item with its priority score."""

    item: T
    priority: float

    def __iter__(self):
        return iter((self.item, self.priority))


class RedisPriorityQueue(Generic[T]):
    """
    A Redis-backed priority queue using Sorted Sets (ZSET).

    This field is stored separately from the JSON document in a linked ZSET key.
    All sorting and operations are handled natively by Redis with O(log N) complexity.

    Key Pattern: {ModelKey}:pq:{field_name}

    Features:
    - No Lua scripts - uses native Redis ZSET commands
    - O(log N) insertions and deletions
    - O(log N) + O(M) range queries
    - Automatic TTL synchronization with parent model
    - Transparent linking to parent model

    Example:
        class TaskQueue(AtomicRedisModel):
            name: str
            tasks: PriorityQueue[str] = PriorityQueue()

        queue = TaskQueue(name="my_queue")
        await queue.asave()
        await queue.tasks.apush("urgent_task", priority=10.0)
        await queue.tasks.apush("low_priority_task", priority=1.0)

        # Pop highest priority item
        item = await queue.tasks.apop_max()  # Returns "urgent_task"
    """

    field_name: str = None
    _base_model_link: "AtomicRedisModel | RedisType" = None
    _local_cache: list[PriorityItem[T]] = None

    def __init__(self, items: list[PriorityItem[T]] | None = None):
        self._base_model_link = None
        self.field_name = None
        self._local_cache = items or []

    @property
    def redis(self):
        return self._base_model_link.Meta.redis

    @property
    def Meta(self):
        return self._base_model_link.Meta

    @property
    def pipeline(self):
        return _context_var.get()

    @property
    def client(self):
        return _context_var.get() or self.redis

    @property
    def parent_key(self) -> str:
        """Get the parent model's Redis key."""
        return self._base_model_link.key

    @property
    def zset_key(self) -> str:
        """
        Get the ZSET key for this priority queue.

        Key format: {ModelKey}:pq:{field_name}
        Example: User:abc123:pq:tasks
        """
        field = self.field_name.lstrip(".")
        return f"{self.parent_key}:pq:{field}"

    def _serialize_member(self, item: T) -> str:
        """Serialize an item for storage in Redis ZSET."""
        if isinstance(item, (str, int, float)):
            return str(item)
        import json

        return json.dumps(item)

    def _deserialize_member(self, member: str) -> T:
        """Deserialize a member from Redis ZSET."""
        import json

        try:
            return json.loads(member)
        except (json.JSONDecodeError, TypeError):
            return member

    async def _refresh_ttl(self):
        """Refresh TTL for the ZSET key if configured."""
        if self.Meta.ttl is not None and self.Meta.refresh_ttl:
            await self.client.expire(self.zset_key, self.Meta.ttl)

    async def _sync_ttl_with_parent(self):
        """Sync TTL of ZSET with parent model's key."""
        if self.Meta.ttl is not None:
            ttl = await self.redis.ttl(self.parent_key)
            if ttl > 0:
                await self.client.expire(self.zset_key, ttl)

    # ==================== Core Operations ====================

    async def apush(self, item: T, priority: float) -> int:
        """
        Add an item to the priority queue with the given priority score.

        Uses Redis ZADD command - O(log N).

        Args:
            item: The item to add
            priority: The priority score (higher = higher priority)

        Returns:
            Number of elements added (1 if new, 0 if updated)
        """
        member = self._serialize_member(item)
        result = await self.client.zadd(self.zset_key, {member: priority})
        self._local_cache.append(PriorityItem(item, priority))
        await self._refresh_ttl()
        return result

    async def apush_many(self, items: list[tuple[T, float]]) -> int:
        """
        Add multiple items with their priorities.

        Uses Redis ZADD with multiple members - O(log N) per item.

        Args:
            items: List of (item, priority) tuples

        Returns:
            Number of elements added
        """
        if not items:
            return 0
        mapping = {self._serialize_member(item): priority for item, priority in items}
        result = await self.client.zadd(self.zset_key, mapping)
        for item, priority in items:
            self._local_cache.append(PriorityItem(item, priority))
        await self._refresh_ttl()
        return result

    async def apop_min(self, count: int = 1) -> list[PriorityItem[T]] | PriorityItem[T] | None:
        """
        Remove and return the item(s) with the lowest priority.

        Uses Redis ZPOPMIN - O(log N) per item.

        Args:
            count: Number of items to pop

        Returns:
            Single PriorityItem if count=1, list of PriorityItems otherwise, None if empty
        """
        results = await self.client.zpopmin(self.zset_key, count)
        await self._refresh_ttl()

        if not results:
            return None if count == 1 else []

        items = [
            PriorityItem(self._deserialize_member(member), score)
            for member, score in results
        ]

        return items[0] if count == 1 else items

    async def apop_max(self, count: int = 1) -> list[PriorityItem[T]] | PriorityItem[T] | None:
        """
        Remove and return the item(s) with the highest priority.

        Uses Redis ZPOPMAX - O(log N) per item.

        Args:
            count: Number of items to pop

        Returns:
            Single PriorityItem if count=1, list of PriorityItems otherwise, None if empty
        """
        results = await self.client.zpopmax(self.zset_key, count)
        await self._refresh_ttl()

        if not results:
            return None if count == 1 else []

        items = [
            PriorityItem(self._deserialize_member(member), score)
            for member, score in results
        ]

        return items[0] if count == 1 else items

    async def apeek_min(self, count: int = 1) -> list[PriorityItem[T]] | PriorityItem[T] | None:
        """
        Return the item(s) with the lowest priority without removing.

        Uses Redis ZRANGE with LIMIT - O(log N + M).

        Args:
            count: Number of items to peek

        Returns:
            Single PriorityItem if count=1, list of PriorityItems otherwise, None if empty
        """
        results = await self.client.zrange(
            self.zset_key, 0, count - 1, withscores=True
        )
        await refresh_ttl_if_needed(
            self.client, self.zset_key, self.Meta.ttl, self.Meta.refresh_ttl
        )

        if not results:
            return None if count == 1 else []

        items = [
            PriorityItem(self._deserialize_member(member), score)
            for member, score in results
        ]

        return items[0] if count == 1 else items

    async def apeek_max(self, count: int = 1) -> list[PriorityItem[T]] | PriorityItem[T] | None:
        """
        Return the item(s) with the highest priority without removing.

        Uses Redis ZREVRANGE with LIMIT - O(log N + M).

        Args:
            count: Number of items to peek

        Returns:
            Single PriorityItem if count=1, list of PriorityItems otherwise, None if empty
        """
        results = await self.client.zrevrange(
            self.zset_key, 0, count - 1, withscores=True
        )
        await refresh_ttl_if_needed(
            self.client, self.zset_key, self.Meta.ttl, self.Meta.refresh_ttl
        )

        if not results:
            return None if count == 1 else []

        items = [
            PriorityItem(self._deserialize_member(member), score)
            for member, score in results
        ]

        return items[0] if count == 1 else items

    # ==================== Query Operations ====================

    async def arange(
        self, start: int = 0, stop: int = -1, withscores: bool = True
    ) -> list[PriorityItem[T]] | list[T]:
        """
        Get items by index range (sorted by priority ascending).

        Uses Redis ZRANGE - O(log N + M).

        Args:
            start: Start index (0-based)
            stop: Stop index (-1 for all)
            withscores: Include priority scores in result

        Returns:
            List of PriorityItems if withscores=True, list of items otherwise
        """
        results = await self.client.zrange(
            self.zset_key, start, stop, withscores=withscores
        )
        await refresh_ttl_if_needed(
            self.client, self.zset_key, self.Meta.ttl, self.Meta.refresh_ttl
        )

        if withscores:
            return [
                PriorityItem(self._deserialize_member(member), score)
                for member, score in results
            ]
        return [self._deserialize_member(member) for member in results]

    async def arange_by_score(
        self,
        min_score: float = float("-inf"),
        max_score: float = float("inf"),
        withscores: bool = True,
        offset: int = 0,
        count: int | None = None,
    ) -> list[PriorityItem[T]] | list[T]:
        """
        Get items within a score (priority) range.

        Uses Redis ZRANGEBYSCORE - O(log N + M).

        Args:
            min_score: Minimum priority (inclusive)
            max_score: Maximum priority (inclusive)
            withscores: Include priority scores in result
            offset: Number of items to skip
            count: Maximum number of items to return

        Returns:
            List of PriorityItems if withscores=True, list of items otherwise
        """
        results = await self.client.zrangebyscore(
            self.zset_key,
            min_score,
            max_score,
            withscores=withscores,
            start=offset if count else None,
            num=count,
        )
        await refresh_ttl_if_needed(
            self.client, self.zset_key, self.Meta.ttl, self.Meta.refresh_ttl
        )

        if withscores:
            return [
                PriorityItem(self._deserialize_member(member), score)
                for member, score in results
            ]
        return [self._deserialize_member(member) for member in results]

    async def arank(self, item: T) -> int | None:
        """
        Get the rank (position) of an item in the queue (0 = lowest priority).

        Uses Redis ZRANK - O(log N).

        Args:
            item: The item to find

        Returns:
            Rank (0-based) or None if not found
        """
        member = self._serialize_member(item)
        result = await self.client.zrank(self.zset_key, member)
        await refresh_ttl_if_needed(
            self.client, self.zset_key, self.Meta.ttl, self.Meta.refresh_ttl
        )
        return result

    async def arevrank(self, item: T) -> int | None:
        """
        Get the reverse rank (position) of an item (0 = highest priority).

        Uses Redis ZREVRANK - O(log N).

        Args:
            item: The item to find

        Returns:
            Reverse rank (0-based) or None if not found
        """
        member = self._serialize_member(item)
        result = await self.client.zrevrank(self.zset_key, member)
        await refresh_ttl_if_needed(
            self.client, self.zset_key, self.Meta.ttl, self.Meta.refresh_ttl
        )
        return result

    async def ascore(self, item: T) -> float | None:
        """
        Get the priority score of an item.

        Uses Redis ZSCORE - O(1).

        Args:
            item: The item to find

        Returns:
            Priority score or None if not found
        """
        member = self._serialize_member(item)
        result = await self.client.zscore(self.zset_key, member)
        await refresh_ttl_if_needed(
            self.client, self.zset_key, self.Meta.ttl, self.Meta.refresh_ttl
        )
        return result

    async def acontains(self, item: T) -> bool:
        """
        Check if an item exists in the queue.

        Uses Redis ZSCORE - O(1).

        Args:
            item: The item to check

        Returns:
            True if item exists, False otherwise
        """
        return await self.ascore(item) is not None

    # ==================== Modification Operations ====================

    async def aremove(self, item: T) -> bool:
        """
        Remove an item from the queue.

        Uses Redis ZREM - O(log N).

        Args:
            item: The item to remove

        Returns:
            True if removed, False if not found
        """
        member = self._serialize_member(item)
        result = await self.client.zrem(self.zset_key, member)
        await self._refresh_ttl()
        return result == 1

    async def aremove_many(self, *items: T) -> int:
        """
        Remove multiple items from the queue.

        Uses Redis ZREM with multiple members - O(log N) per item.

        Args:
            *items: Items to remove

        Returns:
            Number of items removed
        """
        if not items:
            return 0
        members = [self._serialize_member(item) for item in items]
        result = await self.client.zrem(self.zset_key, *members)
        await self._refresh_ttl()
        return result

    async def aupdate_priority(self, item: T, priority: float) -> bool:
        """
        Update the priority of an existing item.

        Uses Redis ZADD with XX flag - O(log N).

        Args:
            item: The item to update
            priority: The new priority score

        Returns:
            True if updated, False if item not found
        """
        member = self._serialize_member(item)
        # XX: Only update existing elements, don't add new ones
        result = await self.client.zadd(self.zset_key, {member: priority}, xx=True, ch=True)
        await self._refresh_ttl()
        return result == 1

    async def aincrement_priority(self, item: T, increment: float) -> float | None:
        """
        Increment the priority of an item by a given amount.

        Uses Redis ZINCRBY - O(log N).

        Args:
            item: The item to update
            increment: Amount to add to the priority (can be negative)

        Returns:
            New priority score, or None if item doesn't exist
        """
        member = self._serialize_member(item)
        # Check if member exists first
        if not await self.acontains(item):
            return None
        result = await self.client.zincrby(self.zset_key, increment, member)
        await self._refresh_ttl()
        return result

    async def aclear(self) -> bool:
        """
        Remove all items from the queue.

        Uses Redis DEL - O(1).

        Returns:
            True if key was deleted, False if it didn't exist
        """
        result = await self.client.delete(self.zset_key)
        self._local_cache.clear()
        return result == 1

    # ==================== Utility Operations ====================

    async def alen(self) -> int:
        """
        Get the number of items in the queue.

        Uses Redis ZCARD - O(1).

        Returns:
            Number of items
        """
        result = await self.client.zcard(self.zset_key)
        await refresh_ttl_if_needed(
            self.client, self.zset_key, self.Meta.ttl, self.Meta.refresh_ttl
        )
        return result

    async def acount_by_score(
        self, min_score: float = float("-inf"), max_score: float = float("inf")
    ) -> int:
        """
        Count items within a score range.

        Uses Redis ZCOUNT - O(log N).

        Args:
            min_score: Minimum priority (inclusive)
            max_score: Maximum priority (inclusive)

        Returns:
            Number of items in the range
        """
        result = await self.client.zcount(self.zset_key, min_score, max_score)
        await refresh_ttl_if_needed(
            self.client, self.zset_key, self.Meta.ttl, self.Meta.refresh_ttl
        )
        return result

    async def aitems_with_scores(self) -> list[PriorityItem[T]]:
        """
        Get all items with their priority scores.

        Uses Redis ZRANGE WITHSCORES - O(N).

        Returns:
            List of PriorityItems
        """
        return await self.arange(0, -1, withscores=True)

    async def aitems(self) -> list[T]:
        """
        Get all items without scores (sorted by priority ascending).

        Uses Redis ZRANGE - O(N).

        Returns:
            List of items
        """
        return await self.arange(0, -1, withscores=False)

    async def aexists(self) -> bool:
        """
        Check if the priority queue key exists in Redis.

        Uses Redis EXISTS - O(1).

        Returns:
            True if key exists, False otherwise
        """
        return await self.client.exists(self.zset_key) == 1

    async def adelete_key(self) -> bool:
        """
        Delete the ZSET key from Redis.

        Uses Redis DEL - O(1).

        Returns:
            True if deleted, False if didn't exist
        """
        return await self.client.delete(self.zset_key) == 1

    # ==================== Lifecycle Hooks ====================

    async def on_model_save(self):
        """Called when the parent model is saved."""
        # Sync TTL with parent model
        await self._sync_ttl_with_parent()

    async def on_model_delete(self):
        """Called when the parent model is deleted."""
        # Delete the ZSET key when parent is deleted
        await self.adelete_key()

    async def on_model_load(self):
        """Called when the parent model is loaded."""
        # Clear local cache as it may be stale
        self._local_cache.clear()

    # ==================== Pydantic Integration ====================

    def clone(self):
        """Create a deep copy of the priority queue."""
        return RedisPriorityQueue(items=list(self._local_cache))

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """
        Pydantic schema for the priority queue.

        The priority queue is excluded from JSON serialization as it's stored
        in a separate Redis key.
        """
        return core_schema.with_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._serialize, info_arg=False
            ),
        )

    @classmethod
    def _validate(cls, value: Any, info) -> "RedisPriorityQueue[T]":
        """Validate and create a RedisPriorityQueue instance."""
        if isinstance(value, cls):
            return value
        if value is None:
            return cls()
        if isinstance(value, list):
            items = [
                PriorityItem(item=v.get("item") if isinstance(v, dict) else v,
                            priority=v.get("priority", 0.0) if isinstance(v, dict) else 0.0)
                for v in value
            ]
            return cls(items=items)
        return cls()

    @classmethod
    def _serialize(cls, value: "RedisPriorityQueue[T]") -> None:
        """
        Serialize the priority queue.

        Returns None because the data is stored in a separate ZSET key,
        not in the JSON document.
        """
        # Priority queue data is stored separately, so we exclude it from JSON
        return None

    def __len__(self) -> int:
        """Return the length of the local cache (use alen() for Redis count)."""
        return len(self._local_cache)

    def __bool__(self) -> bool:
        """Return True if queue has items locally or potentially in Redis."""
        return len(self._local_cache) > 0

    def __repr__(self) -> str:
        key = self.zset_key if self._base_model_link else "<unlinked>"
        return f"RedisPriorityQueue(key={key}, local_items={len(self._local_cache)})"


# Type alias for cleaner imports
if TYPE_CHECKING:
    from typing import TypeAlias

    RedisPriorityQueue: TypeAlias = RedisPriorityQueue[T]  # pragma: no cover
