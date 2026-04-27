import json
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar, get_args

from pydantic import GetCoreSchemaHandler, TypeAdapter
from pydantic_core import core_schema

from rapyer.actions import ActionGroup, mark_actions
from rapyer.types.special import SpecialFieldType

T = TypeVar("T")


@dataclass
class PriorityQueueItem(Generic[T]):
    value: T
    priority: float


class RedisPriorityQueue(SpecialFieldType, Generic[T]):
    """
    Priority queue backed by a Redis Sorted Set. Pure Redis proxy — no local state.

    All operations go directly to Redis via ``self.client`` (pipeline-aware).
    Lower priority score = higher precedence.
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
            raw = raw.decode()
        parsed = json.loads(raw)
        if self._value_adapter:
            return self._value_adapter.validate_python(parsed)
        return parsed

    # --- Queue operations ---

    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND)
    async def apush(self, value: T, priority: float):
        serialized = self._serialize_value(value)
        await self.client.zadd(self.special_key, {serialized: priority})

    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND)
    async def apush_many(self, items: list[PriorityQueueItem[T]]):
        mapping = {self._serialize_value(item.value): item.priority for item in items}
        await self.client.zadd(self.special_key, mapping)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE, ActionGroup.READ)
    async def apop(self):
        result = await self.redis.zpopmin(self.special_key, count=1)
        if not result:
            return None
        member, score = result[0]
        return self._deserialize_value(member)

    @mark_actions(ActionGroup.READ)
    async def apeek(self):
        """Return the item with the lowest priority score without removing it."""
        result = await self.redis.zrange(self.special_key, 0, 0, withscores=True)
        if not result:
            return None
        member, score = result[0]
        return self._deserialize_value(member)

    @mark_actions(ActionGroup.READ)
    async def asize(self) -> int:
        """Return the number of items in the queue."""
        return await self.client.zcard(self.special_key)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE)
    async def aclear(self):
        """Remove all items from the queue."""
        await self.client.delete(self.special_key)

    @mark_actions(ActionGroup.READ)
    async def aitems(self) -> list[PriorityQueueItem]:
        """Return all items sorted by priority (ascending)."""
        result = await self.redis.zrange(self.special_key, 0, -1, withscores=True)
        return [
            PriorityQueueItem(value=self._deserialize_value(m), priority=s)
            for m, s in result
        ]

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE)
    async def aremove(self, value) -> Optional[bool]:
        """Remove a specific value from the queue. Returns True if removed. In pipeline it returns None"""
        serialized = self._serialize_value(value)
        removed = await self.client.zrem(self.special_key, serialized)
        if self.pipeline:
            return None
        return removed > 0

    # --- SpecialFieldType interface ---

    async def asave_special(self):
        # NOTE - nothing to save
        pass

    async def adelete_special(self):
        await self.client.delete(self.special_key)

    async def aduplicate_special(self, target_special_key: str):
        items = await self.redis.zrange(self.special_key, 0, -1, withscores=True)
        if items:
            mapping = {member: score for member, score in items}
            await self.client.zadd(target_special_key, mapping)

    def __eq__(self, other):
        if not isinstance(other, RedisPriorityQueue):
            return False
        return self.special_key == other.special_key

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
