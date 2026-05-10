import json
from typing import Any, Generic, Iterable, Optional, TypeVar, get_args

from pydantic import GetCoreSchemaHandler, TypeAdapter
from pydantic_core import core_schema

from rapyer.actions import ActionGroup, mark_actions
from rapyer.types.special import SpecialFieldType

T = TypeVar("T")


class RedisSet(SpecialFieldType, Generic[T]):
    """
    Unordered, unique-member collection backed by a Redis SET. Pure Redis proxy —
    no local state.
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

    # --- Core operations ---

    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND, version="v2")
    async def aadd(self, value: T):
        await self.client.sadd(self.special_key, self._serialize_value(value))

    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND, version="v2")
    async def aadd_many(self, values: Iterable[T]):
        serialized = [self._serialize_value(v) for v in values]
        if serialized:
            await self.client.sadd(self.special_key, *serialized)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE, version="v2")
    async def aremove(self, value: T) -> Optional[bool]:
        removed = await self.client.srem(self.special_key, self._serialize_value(value))
        if self.pipeline:
            return None
        return removed > 0

    @mark_actions(ActionGroup.READ, version="v2")
    async def acontains(self, value: T) -> bool:
        return bool(
            await self.redis.sismember(self.special_key, self._serialize_value(value))
        )

    @mark_actions(ActionGroup.READ, version="v2")
    async def amembers(self) -> set[T]:
        raw = await self.redis.smembers(self.special_key)
        return {self._deserialize_value(m) for m in raw}

    @mark_actions(ActionGroup.READ, version="v2")
    async def asize(self) -> int:
        return await self.redis.scard(self.special_key)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE, ActionGroup.READ, version="v2")
    async def apop(self) -> Optional[T]:
        raw = await self.redis.spop(self.special_key)
        if raw is None:
            return None
        return self._deserialize_value(raw)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE, version="v2")
    async def aclear(self):
        await self.client.delete(self.special_key)

    # --- Multi-set algebra ---

    @mark_actions(ActionGroup.READ, version="v2")
    async def aunion(self, *others: "RedisSet[T]") -> set[T]:
        keys = [self.special_key, *(o.special_key for o in others)]
        raw = await self.redis.sunion(*keys)
        return {self._deserialize_value(m) for m in raw}

    @mark_actions(ActionGroup.READ, version="v2")
    async def aintersect(self, *others: "RedisSet[T]") -> set[T]:
        keys = [self.special_key, *(o.special_key for o in others)]
        raw = await self.redis.sinter(*keys)
        return {self._deserialize_value(m) for m in raw}

    @mark_actions(ActionGroup.READ, version="v2")
    async def adifference(self, *others: "RedisSet[T]") -> set[T]:
        keys = [self.special_key, *(o.special_key for o in others)]
        raw = await self.redis.sdiff(*keys)
        return {self._deserialize_value(m) for m in raw}

    # --- SpecialFieldType interface ---

    async def asave_special(self):
        # NOTE - nothing to save; every op writes through to Redis directly.
        pass

    async def adelete_special(self):
        await self.client.delete(self.special_key)

    async def aduplicate_special(self, target_special_key: str):
        members = await self.redis.smembers(self.special_key)
        if members:
            await self.client.sadd(target_special_key, *members)

    def __eq__(self, other):
        if not isinstance(other, RedisSet):
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
