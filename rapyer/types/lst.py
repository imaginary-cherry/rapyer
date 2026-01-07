import json
from typing import TypeVar, TYPE_CHECKING

from pydantic_core import core_schema
from pydantic_core.core_schema import ValidationInfo, SerializationInfo
from typing_extensions import TypeAlias

from rapyer.types.base import GenericRedisType, RedisType, REDIS_DUMP_FLAG_NAME
from rapyer.utils.redis import refresh_ttl_if_needed

T = TypeVar("T")


class RedisList(list, GenericRedisType[T]):
    original_type = list

    def __init__(self, *args, **kwargs):
        list.__init__(self, *args, **kwargs)
        GenericRedisType.__init__(self, *args, **kwargs)

    def create_new_values(self, keys, values):
        new_values = self._adapter.validate_python(values)
        for key, value in zip(keys, new_values):
            self.init_redis_field(f"[{key}]", value)
        return new_values

    def create_new_value(self, key, value):
        new_val = self.create_new_values([key], [value])[0]
        return new_val

    def sub_field_path(self, key: str):
        return f"{self.field_path}[{key}]"

    def __setitem__(self, key, value):
        if self.pipeline:
            self.pipeline.json().set(self.key, self.json_field_path(key), value)
        new_val = self.create_new_value(key, value)
        return super().__setitem__(key, new_val)

    def __iadd__(self, other):
        self.extend(other)
        return self

    def append(self, __object):
        if self.pipeline:
            self.pipeline.json().arrappend(self.key, self.json_path, __object)
        key = len(self)
        new_val = self.create_new_value(key, __object)
        return super().append(new_val)

    def extend(self, new_lst):
        if self.pipeline and new_lst:
            self.pipeline.json().arrappend(self.key, self.json_path, *new_lst)
        new_keys = range(len(self), len(self) + len(new_lst))
        new_vals = self.create_new_values(list(new_keys), new_lst)
        return super().extend(new_vals)

    def insert(self, index, __object):
        if self.pipeline:
            self.pipeline.json().arrinsert(self.key, self.json_path, index, __object)
        new_val = self.create_new_value(index, __object)
        return super().insert(index, new_val)

    def clear(self):
        if self.pipeline:
            self.pipeline.json().set(self.key, self.json_path, [])
        return super().clear()

    async def aappend(self, __object):
        self.append(__object)

        # Serialize the object for Redis storage using a type adapter
        if not self.pipeline:
            serialized_object = self._adapter.dump_python(
                [__object], mode="json", context={REDIS_DUMP_FLAG_NAME: True}
            )
            await self.redis.json().arrappend(
                self.key, self.json_path, *serialized_object
            )
            await refresh_ttl_if_needed(
                self.redis, self.key, self.Meta.ttl, self.Meta.refresh_ttl
            )

    async def aextend(self, __iterable):
        items = list(__iterable)
        self.extend(items)

        # Convert iterable to list and serialize items using type adapter
        if items and not self.pipeline:
            # normalized_items = self._adapter.validate_python(items)
            serialized_items = self._adapter.dump_python(
                items, mode="json", context={REDIS_DUMP_FLAG_NAME: True}
            )
            await self.redis.json().arrappend(
                self.key,
                self.json_path,
                *serialized_items,
            )
            await refresh_ttl_if_needed(
                self.redis, self.key, self.Meta.ttl, self.Meta.refresh_ttl
            )

    async def apop(self, index=-1):
        if self:
            self.pop(index)
        arrpop = await self.redis.json().arrpop(self.key, self.json_path, index)
        await refresh_ttl_if_needed(
            self.redis, self.key, self.Meta.ttl, self.Meta.refresh_ttl
        )

        # Handle case where arrpop returns [None] for an empty list
        if arrpop[0] is None:
            return None
        arrpop = [json.loads(val) for val in arrpop]
        return self._adapter.validate_python(
            arrpop, context={REDIS_DUMP_FLAG_NAME: True}
        )[0]

    async def ainsert(self, index, __object):
        self.insert(index, __object)

        if not self.pipeline:
            # Serialize the object for Redis storage using a type adapter
            serialized_object = self._adapter.dump_python(
                [__object], mode="json", context={REDIS_DUMP_FLAG_NAME: True}
            )
            await self.redis.json().arrinsert(
                self.key, self.json_path, index, *serialized_object
            )
            await refresh_ttl_if_needed(
                self.redis, self.key, self.Meta.ttl, self.Meta.refresh_ttl
            )

    async def aclear(self):
        # Clear local list
        self.clear()

        # Clear Redis list
        if not self.pipeline:
            await self.client.json().set(self.key, self.json_path, [])
            await refresh_ttl_if_needed(
                self.client, self.key, self.Meta.ttl, self.Meta.refresh_ttl
            )

    def clone(self):
        return [v.clone() if isinstance(v, RedisType) else v for v in self]

    def iterate_items(self):
        keys = [f"[{i}]" for i in range(len(self))]
        return zip(keys, self)

    @classmethod
    def full_serializer(cls, value, info: SerializationInfo):
        ctx = info.context or {}
        is_redis_data = ctx.get(REDIS_DUMP_FLAG_NAME)
        return [
            cls.serialize_unknown(item) if is_redis_data else item for item in value
        ]

    @classmethod
    def full_deserializer(cls, value: list, info: ValidationInfo):
        ctx = info.context or {}
        is_redis_data = ctx.get(REDIS_DUMP_FLAG_NAME)

        return [
            cls.deserialize_unknown(item) if is_redis_data else item for item in value
        ]

    @classmethod
    def schema_for_unknown(cls):
        core_schema.list_schema(core_schema.str_schema())


if TYPE_CHECKING:
    RedisList: TypeAlias = RedisList[T] | list[T]  # pragma: no cover
