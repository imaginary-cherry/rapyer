import json
import uuid
from typing import Any, Generic, Iterable, Optional, TypeVar, get_origin

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from rapyer.actions import ActionGroup, mark_actions
from rapyer.types.base import REDIS_DUMP_FLAG_NAME
from rapyer.types.special import SpecialFieldType
from rapyer.utils.pythonic import resolve_generic_args, safe_issubclass

T = TypeVar("T")


class RedisSet(set, SpecialFieldType[None], Generic[T]):
    """
    Unordered, unique-member collection backed by a Redis SET. Pure Redis proxy —
    no local state.
    """

    LUA_SNIPPET_DIR = "redis_set"

    def __init__(self, *args, **kwargs):
        set.__init__(self, *args, **kwargs)
        SpecialFieldType.__init__(self)

    @classmethod
    def contains_fk_field(cls) -> bool:
        """True when this set's member type is a foreign-key reference."""
        from rapyer.types.relational import RelationalFieldType

        args = resolve_generic_args(cls)
        inner = args[0] if args else Any
        if inner is Any:
            return False
        inner = get_origin(inner) or inner
        return safe_issubclass(inner, RelationalFieldType)

    @classmethod
    def cascade_container_kind(cls) -> Optional[str]:
        return "set"

    # --- Serialization helpers ---

    def _dump_members(self, values: Iterable[T]) -> list[str]:
        # dump_python never validates, so coerce raw input (e.g. an FK key string) first.
        validated = self._adapter.validate_python(set(values))
        return self._adapter.dump_python(
            validated, mode="json", context={REDIS_DUMP_FLAG_NAME: True}
        )

    def _dump_member(self, value: T) -> str:
        return self._dump_members([value])[0]

    def _load_members(self, raw_iterable) -> set:
        return self._adapter.validate_python(
            raw_iterable, context={REDIS_DUMP_FLAG_NAME: True}
        )

    def _tmp_key(self, label: str) -> str:
        return f"{self.special_key}:__tmp_{label}:{uuid.uuid4().hex}"

    # --- Sync set methods ---

    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND)
    def add(self, value: T):
        if self.pipeline:
            self.pipeline.sadd(self.special_key, self._dump_member(value))
        set.add(self, value)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE)
    def discard(self, value: T):
        if self.pipeline:
            self.pipeline.srem(self.special_key, self._dump_member(value))
        set.discard(self, value)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE)
    def remove(self, value: T):
        if self.pipeline:
            # The queued SREM reconciles state on exit, so a stale mirror must not raise here.
            self.pipeline.srem(self.special_key, self._dump_member(value))
            set.discard(self, value)
        else:
            # Nothing is queued to reconcile, so match native set.remove and raise on a miss.
            set.remove(self, value)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE)
    def clear(self):
        if self.pipeline:
            self.pipeline.delete(self.special_key)
        set.clear(self)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND)
    def update(self, *iterables: Iterable[T]):
        all_values = [v for it in iterables for v in it]
        if not all_values:
            return
        if self.pipeline:
            self.pipeline.sadd(self.special_key, *self._dump_members(all_values))
        set.update(self, all_values)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE)
    def difference_update(self, *iterables: Iterable[T]):
        all_values = [v for it in iterables for v in it]
        if not all_values:
            return
        if self.pipeline:
            self.pipeline.srem(self.special_key, *self._dump_members(all_values))
        set.difference_update(self, all_values)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE)
    def intersection_update(self, *iterables: Iterable[T]):
        # Redis side: one temp set per iterable, SINTERSTORE writes the intersection of self_key
        # with all the temps back into self_key, then the temps are deleted.
        materialized = [set(it) for it in iterables]
        if self.pipeline and materialized:
            temp_keys = []
            for it in materialized:
                temp_key = self._tmp_key("inter")
                members = self._dump_members(it)
                if members:
                    self.pipeline.sadd(temp_key, *members)
                temp_keys.append(temp_key)
            self.pipeline.sinterstore(self.special_key, self.special_key, *temp_keys)
            self.pipeline.delete(*temp_keys)
        # The local mirror recomputes independently, so local state never feeds back into Redis.
        set.intersection_update(self, *materialized)

    @mark_actions(ActionGroup.UPDATE)
    def symmetric_difference_update(self, other: Iterable[T]):
        # A ⊖ B = (A − B) ∪ (B − A), done on Redis with two SDIFFSTOREs plus a SUNIONSTORE.
        other = set(other)
        if self.pipeline:
            other_key = self._tmp_key("symdiff_b")
            only_a_key = self._tmp_key("symdiff_only_a")
            only_b_key = self._tmp_key("symdiff_only_b")
            other_members = self._dump_members(other)
            if other_members:
                self.pipeline.sadd(other_key, *other_members)
            self.pipeline.sdiffstore(only_a_key, self.special_key, other_key)
            self.pipeline.sdiffstore(only_b_key, other_key, self.special_key)
            self.pipeline.sunionstore(self.special_key, only_a_key, only_b_key)
            self.pipeline.delete(other_key, only_a_key, only_b_key)
        set.symmetric_difference_update(self, other)

    def __ior__(self, other):
        self.update(other)
        return self

    def __iand__(self, other):
        self.intersection_update(other)
        return self

    def __isub__(self, other):
        self.difference_update(other)
        return self

    def __ixor__(self, other):
        self.symmetric_difference_update(other)
        return self

    # --- Async mutators (Redis-backed; also update local mirror) ---

    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND)
    async def aadd(self, value: T):
        await self.client.sadd(self.special_key, self._dump_member(value))
        set.add(self, value)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND)
    async def aadd_many(self, values: Iterable[T]):
        values = list(values)
        if not values:
            return
        await self.client.sadd(self.special_key, *self._dump_members(values))
        set.update(self, values)

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE)
    async def aremove(self, value: T) -> Optional[bool]:
        removed = await self.client.srem(self.special_key, self._dump_member(value))
        set.discard(self, value)
        if self.pipeline:
            return None
        return removed > 0

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE, ActionGroup.READ)
    async def apop(self) -> Optional[T]:
        # SPOP lets Redis pick the member atomically; sync ``pop`` picks from the local mirror.
        raw = await self.redis.spop(self.special_key)
        if raw is None:
            return None
        (value,) = self._load_members([raw])
        set.discard(self, value)
        return value

    @mark_actions(ActionGroup.UPDATE, ActionGroup.ERASE)
    async def aclear(self):
        await self.client.delete(self.special_key)
        set.clear(self)

    # --- Async reads ---

    @mark_actions(ActionGroup.READ)
    async def acontains(self, value: T) -> bool:
        return bool(
            await self.redis.sismember(self.special_key, self._dump_member(value))
        )

    @mark_actions(ActionGroup.READ)
    async def amembers(self) -> set:
        raw = await self.redis.smembers(self.special_key)
        return self._load_members(raw)

    @mark_actions(ActionGroup.READ)
    async def asize(self) -> int:
        return await self.redis.scard(self.special_key)

    # --- Multi-set algebra ---

    @mark_actions(ActionGroup.READ)
    async def aunion(self, *others: "RedisSet[T]") -> set:
        keys = [self.special_key, *(o.special_key for o in others)]
        return self._load_members(await self.redis.sunion(*keys))

    @mark_actions(ActionGroup.READ)
    async def aintersect(self, *others: "RedisSet[T]") -> set:
        keys = [self.special_key, *(o.special_key for o in others)]
        return self._load_members(await self.redis.sinter(*keys))

    @mark_actions(ActionGroup.READ)
    async def adifference(self, *others: "RedisSet[T]") -> set:
        keys = [self.special_key, *(o.special_key for o in others)]
        return self._load_members(await self.redis.sdiff(*keys))

    # --- SpecialFieldType lifecycle ---

    async def asave_special(self):
        await self.client.delete(self.special_key)
        if self:
            await self.client.sadd(self.special_key, *self._dump_members(self))

    async def adelete_special(self):
        await self.client.delete(self.special_key)

    async def aduplicate_special(self, target_special_key: str):
        members = await self.redis.smembers(self.special_key)
        if members:
            await self.client.sadd(target_special_key, *members)

    def lua_save_payload(self) -> str:
        if not self:
            return ""
        return json.dumps(self._dump_members(self))

    @classmethod
    def queue_special_loads_in_pipeline(
        cls, pipe, key: str, plan: list, parent_path: str = "", field_name: str = ""
    ):
        field_path = f"{parent_path}{field_name}"
        pipe.smembers(cls.special_field_key(key, field_path))
        plan.append([field_name.lstrip(".")])

    def clone(self):
        new = self.__class__()
        set.update(new, self)
        return new

    # --- Pydantic schema ---

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        args = resolve_generic_args(source_type)
        inner = args[0] if args else Any

        def _validate_wrap(v, handler_call, info):
            ctx = info.context or {}
            is_redis = ctx.get(REDIS_DUMP_FLAG_NAME)
            not_redis_set_obj = not isinstance(v, cls)
            if is_redis and not_redis_set_obj:
                v = {json.loads(m) for m in v}
            return cls(handler_call(v))

        def _serialize_wrap(v, serializer, info):
            base = serializer(v)
            ctx = info.context or {}
            if ctx.get(REDIS_DUMP_FLAG_NAME):
                return [json.dumps(m) for m in base]
            return base

        schema = handler(set[inner])
        serialization = core_schema.wrap_serializer_function_ser_schema(
            _serialize_wrap, info_arg=True, schema=schema
        )
        return core_schema.with_info_wrap_validator_function(
            _validate_wrap, schema, serialization=serialization
        )
