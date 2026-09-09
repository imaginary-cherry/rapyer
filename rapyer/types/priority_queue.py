import json
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from rapyer.actions import ActionGroup, mark_actions
from rapyer.errors.base import RapyerSerializationError
from rapyer.types.base import REDIS_DUMP_FLAG_NAME
from rapyer.types.external import FieldTrait
from rapyer.types.special import SpecialFieldType
from rapyer.utils.pythonic import resolve_generic_args

T = TypeVar("T")


@dataclass
class PriorityQueueItem(Generic[T]):
    value: T
    priority: float


class RedisPriorityQueue(SpecialFieldType[None], Generic[T]):
    """
    Priority queue backed by a Redis Sorted Set. Pure Redis proxy — no local state.
    """

    LUA_SNIPPET_DIR = "redis_priority_queue"

    @classmethod
    def cascade_container_kind(cls) -> Optional[str]:
        return "zset"

    @classmethod
    def traits(cls) -> FieldTrait:
        # No LOADS_WITH_DOC: items are fetched lazily by apeek/aitems.
        return (
            FieldTrait.OWNS_KEYS
            | FieldTrait.EXCLUDED_FROM_DOC
            | FieldTrait.HOLDS_LIVE_STATE
        )

    # --- Serialization helpers ---

    def _dump_members(self, values) -> list[str]:
        # dump_python never validates, so coerce raw input (e.g. an FK key string) first.
        validated = self._adapter.validate_python(
            list(values), context={REDIS_DUMP_FLAG_NAME: True}
        )
        serialized = self._adapter.dump_python(
            validated, mode="json", context={REDIS_DUMP_FLAG_NAME: True}
        )
        return [json.dumps(s) for s in serialized]

    def _dump_member(self, value: T) -> str:
        return self._dump_members([value])[0]

    def _load_member(self, raw):
        parsed = json.loads(raw)
        return self._adapter.validate_python(
            [parsed], context={REDIS_DUMP_FLAG_NAME: True}
        )[0]

    # --- Queue operations ---

    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND)
    async def apush(self, value: T, priority: float):
        await self.client.zadd(self.special_key, {self._dump_member(value): priority})

    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND)
    async def apush_many(self, items: list[PriorityQueueItem[T]]):
        if not items:
            return
        serialized = self._dump_members(item.value for item in items)
        mapping = {s: item.priority for s, item in zip(serialized, items)}
        await self.client.zadd(self.special_key, mapping)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE, ActionGroup.READ)
    async def apop(self):
        result = await self.redis.zpopmin(self.special_key, count=1)
        if not result:
            return None
        member, score = result[0]
        return self._load_member(member)

    @mark_actions(ActionGroup.READ)
    async def apeek(self):
        result = await self.redis.zrange(self.special_key, 0, 0, withscores=True)
        if not result:
            return None
        member, score = result[0]
        return self._load_member(member)

    @mark_actions(ActionGroup.READ)
    async def asize(self) -> int:
        return await self.redis.zcard(self.special_key)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE)
    async def aclear(self):
        await self.client.delete(self.special_key)

    @mark_actions(ActionGroup.READ)
    async def aitems(self) -> list[PriorityQueueItem]:
        result = await self.redis.zrange(self.special_key, 0, -1, withscores=True)
        return [
            PriorityQueueItem(value=self._load_member(m), priority=s) for m, s in result
        ]

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE)
    async def aremove(self, value) -> Optional[bool]:
        removed = await self.client.zrem(self.special_key, self._dump_member(value))
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

    @classmethod
    def has_lua_load_output(cls) -> bool:
        return False

    def __eq__(self, other):
        if not isinstance(other, RedisPriorityQueue):
            return False
        return self.special_key == other.special_key

    # --- Pydantic schema ---

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        args = resolve_generic_args(source_type)
        inner = args[0] if args else Any

        def _validate_wrap(v, handler_call, info):
            if isinstance(v, cls):
                return v
            if isinstance(v, RedisPriorityQueue):
                # An unconverted instance, e.g. from ``default_factory``. RedisPriorityQueue is a
                # pure Redis proxy with no local state, so re-wrapping only rebinds field_name.
                return cls()
            if isinstance(v, list):
                if (info.context or {}).get(REDIS_DUMP_FLAG_NAME):
                    return handler_call(v)
                raise ValueError(
                    f"Cannot initialize {RedisPriorityQueue.__name__} from a list — "
                    "assign a RedisPriorityQueue instance instead."
                )
            raise RapyerSerializationError(
                f"PriorityQueue can serialize list or Prioirty queue object only, got {type(v)}"
            )

        def _serialize(v, serializer):
            if isinstance(v, list):
                return serializer(v)  # ← let pydantic serialize as list[T]
            return v

        schema = handler(list[inner])
        serialization = core_schema.wrap_serializer_function_ser_schema(
            _serialize, schema=schema
        )
        return core_schema.with_info_wrap_validator_function(
            _validate_wrap, schema, serialization=serialization
        )
