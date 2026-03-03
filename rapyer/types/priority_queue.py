import json
from typing import Any, TypeVar, Generic, get_args

from pydantic import GetCoreSchemaHandler, TypeAdapter
from pydantic_core import core_schema

from rapyer.types.special import SpecialFieldType

T = TypeVar("T")


class RedisPriorityQueue(SpecialFieldType, Generic[T]):
    """Priority queue backed by a Redis Sorted Set. Pure Redis proxy — no local state.

    All operations go directly to Redis via ``self.client`` (pipeline-aware).
    Lower priority score = higher precedence.

    Usage::

        class MyModel(AtomicRedisModel):
            name: str
            tasks: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue)
    """

    original_type: type = type(None)
    _value_adapter: TypeAdapter = None

    @classmethod
    def find_inner_type(cls, type_):
        args = get_args(type_)
        return args[0] if args else Any

    def _serialize_value(self, value) -> str:
        if self._value_adapter:
            return json.dumps(self._value_adapter.dump_python(value, mode="json"))
        return json.dumps(value)

    def _deserialize_value(self, raw):
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        parsed = json.loads(raw)
        if self._value_adapter:
            return self._value_adapter.validate_python(parsed)
        return parsed

    # --- Queue operations ---

    async def apush(self, value, priority: float) -> None:
        """Add an item with given priority. Lower priority = higher precedence."""
        serialized = self._serialize_value(value)
        await self.client.zadd(self.special_key, {serialized: priority})
        await self.refresh_ttl_if_needed()

    async def apush_many(self, items: list[tuple]) -> None:
        """Add multiple (value, priority) pairs atomically."""
        mapping = {self._serialize_value(v): p for v, p in items}
        await self.client.zadd(self.special_key, mapping)
        await self.refresh_ttl_if_needed()

    async def apop(self):
        """Remove and return the item with the lowest priority score.

        Returns a ``(value, priority)`` tuple, or ``None`` if empty.
        """
        result = await self.client.zpopmin(self.special_key, count=1)
        if not result:
            return None
        member, score = result[0]
        return self._deserialize_value(member), score

    async def apeek(self):
        """Return the item with the lowest priority score without removing it.

        Returns a ``(value, priority)`` tuple, or ``None`` if empty.
        """
        result = await self.client.zrange(
            self.special_key, 0, 0, withscores=True
        )
        if not result:
            return None
        member, score = result[0]
        return self._deserialize_value(member), score

    async def asize(self) -> int:
        """Return the number of items in the queue."""
        return await self.client.zcard(self.special_key)

    async def aclear(self) -> None:
        """Remove all items from the queue."""
        await self.client.delete(self.special_key)

    async def aitems(self) -> list[tuple]:
        """Return all items sorted by priority (ascending)."""
        result = await self.client.zrange(
            self.special_key, 0, -1, withscores=True
        )
        return [(self._deserialize_value(m), s) for m, s in result]

    async def aremove(self, value) -> bool:
        """Remove a specific value from the queue. Returns True if removed."""
        serialized = self._serialize_value(value)
        removed = await self.client.zrem(self.special_key, serialized)
        return removed > 0

    # --- SpecialFieldType interface ---

    async def asave_special(self) -> None:
        pass

    async def adelete_special(self) -> None:
        await self.client.delete(self.special_key)

    # --- Pydantic schema ---

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(
            lambda v: v if isinstance(v, cls) else cls(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: None,
            ),
        )
