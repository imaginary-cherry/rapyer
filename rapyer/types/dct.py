from typing import TypeVar, Generic, get_args, Any, TypeAlias, TYPE_CHECKING

from pydantic_core import core_schema

from rapyer.types.base import GenericRedisType, RedisType, REDIS_DUMP_FLAG_NAME
from rapyer.utils.redis import refresh_ttl_if_needed
from rapyer.utils.redis import update_keys_in_pipeline

T = TypeVar("T")

# Redis Lua script for atomic get-and-delete operation
POP_SCRIPT = """
local key = KEYS[1]
local path = ARGV[1]
local target_key = ARGV[2]

-- Get the value from the JSON object
local value = redis.call('JSON.GET', key, path .. '.' .. target_key)

if value and value ~= '[]' and value ~= 'null' then
    -- Delete the key from the JSON object
    redis.call('JSON.DEL', key, path .. '.' .. target_key)

    -- Parse and return the actual value
    local parsed = cjson.decode(value)
    return parsed[1]  -- Return first element if it's an array
else
    return nil
end
"""


# Redis Lua script for atomic get-arbitrary-key-and-delete operation
POPITEM_SCRIPT = """
local key = KEYS[1]
local path = ARGV[1]

-- Get all the keys from the JSON object
local keys = redis.call('JSON.OBJKEYS', key, path)

-- Return nil if no keys exist
if not keys or #keys == 0 then
    return nil
end

-- Handle nested arrays - Redis sometimes wraps results
if type(keys[1]) == 'table' then
    keys = keys[1]
end

-- Check again after unwrapping
if not keys or #keys == 0 then
    return nil
end

local first_key = tostring(keys[1])

-- Get the value for this key
local value = redis.call('JSON.GET', key, path .. '.' .. first_key)

-- Return nil if value doesn't exist
if not value then
    return nil
end

-- Delete the key from the JSON object
redis.call('JSON.DEL', key, path .. '.' .. first_key)

-- Parse the JSON string
local parsed_value = cjson.decode(value)

-- If it's a table/object, return the first value
if type(parsed_value) == 'table' then
    for _, v in pairs(parsed_value) do
        return {first_key, v}  -- Return first value found
    end
    -- If table is empty, return nil
    return nil
end

-- Otherwise return the parsed value as-is
return {first_key, parsed_value}
"""


class RedisDict(dict[str, T], GenericRedisType, Generic[T]):
    original_type = dict

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        GenericRedisType.__init__(self, *args, **kwargs)

    @classmethod
    def find_inner_type(cls, type_):
        args = get_args(type_)
        return args[1] if len(args) >= 2 else Any

    def validate_dict(self, dct: dict):
        new_dct = self._adapter.validate_python(dct)
        if new_dct:
            for key, value in new_dct.items():
                self.init_redis_field(f".{key}", value)
        return new_dct

    def update(self, m=None, /, **kwargs):
        if self.pipeline:
            m_redis_val = self._adapter.dump_python(
                m, mode="json", context={REDIS_DUMP_FLAG_NAME: True}
            )
            m_redis_val = m_redis_val or {}
            kwargs_redis_val = self._adapter.dump_python(
                kwargs, mode="json", context={REDIS_DUMP_FLAG_NAME: True}
            )
            updated_values = m_redis_val | kwargs_redis_val
            updated_values = {
                self.json_field_path(key): v for key, v in updated_values.items()
            }
            update_keys_in_pipeline(self.pipeline, self.key, **updated_values)
        m_new_val = self.validate_dict(m) if m else {}
        kwargs_new_val = self.validate_dict(kwargs)
        return super().update(m_new_val, **kwargs_new_val)

    def clear(self):
        if self.pipeline:
            self.pipeline.json().set(self.key, self.json_path, {})
        return super().clear()

    def __setitem__(self, key, value):
        if self.pipeline:
            self.pipeline.json().set(self.key, self.json_field_path(key), value)
        new_val = self.validate_dict({key: value})[key]
        super().__setitem__(key, new_val)

    async def aset_item(self, key, value):
        self.__setitem__(key, value)

        # Serialize the value for Redis storage using a type adapter
        serialized_value = self._adapter.dump_python(
            {key: value}, mode="json", context={REDIS_DUMP_FLAG_NAME: True}
        )
        result = await self.client.json().set(
            self.key, self.json_field_path(key), serialized_value[key]
        )
        await refresh_ttl_if_needed(
            self.client, self.key, self.Meta.ttl, self.Meta.refresh_ttl
        )
        return result

    async def adel_item(self, key):
        super().__delitem__(key)
        result = await self.client.json().delete(self.key, self.json_field_path(key))
        await refresh_ttl_if_needed(
            self.client, self.key, self.Meta.ttl, self.Meta.refresh_ttl
        )
        return result

    async def aupdate(self, **kwargs):
        self.update(**kwargs)

        # Serialize values using type adapter
        dumped_data = self._adapter.dump_python(
            kwargs, mode="json", context={REDIS_DUMP_FLAG_NAME: True}
        )
        redis_params = {self.json_field_path(key): v for key, v in dumped_data.items()}

        if not self.pipeline:
            async with self.redis.pipeline() as pipeline:
                update_keys_in_pipeline(pipeline, self.key, **redis_params)
                await pipeline.execute()
            await refresh_ttl_if_needed(
                self.redis, self.key, self.Meta.ttl, self.Meta.refresh_ttl
            )

    async def apop(self, key, default=None):
        # Execute the script atomically
        result = await self.client.eval(POP_SCRIPT, 1, self.key, self.json_path, key)
        # Key exists in Redis, pop from local dict (it should exist there too)
        super().pop(key, None)
        await refresh_ttl_if_needed(
            self.client, self.key, self.Meta.ttl, self.Meta.refresh_ttl
        )

        if result is None:
            # Key doesn't exist in Redis
            return default

        return self._adapter.validate_python(
            {key: result}, context={REDIS_DUMP_FLAG_NAME: True}
        )[key]

    async def apopitem(self):
        # Execute the script atomically
        result = await self.client.eval(POPITEM_SCRIPT, 1, self.key, self.json_path)
        await refresh_ttl_if_needed(
            self.client, self.key, self.Meta.ttl, self.Meta.refresh_ttl
        )

        if result is not None:
            redis_key, redis_value = result
            # Pop the same key from the local dict
            super().pop(
                redis_key.decode() if isinstance(redis_key, bytes) else redis_key
            )
            return self._adapter.validate_python(
                {redis_key: redis_value}, context={REDIS_DUMP_FLAG_NAME: True}
            )[redis_key]
        else:
            # If Redis is empty but local dict has items, raise an error for consistency
            raise KeyError("popitem(): dictionary is empty")

    async def aclear(self):
        self.clear()
        # Clear Redis dict
        result = await self.client.json().set(self.key, self.json_path, {})
        await refresh_ttl_if_needed(
            self.client, self.key, self.Meta.ttl, self.Meta.refresh_ttl
        )
        return result

    def clone(self):
        return {
            k: v.clone() if isinstance(v, RedisType) else v for k, v in self.items()
        }

    def iterate_items(self):
        keys = [f".{k}" for k in self.keys()]
        return zip(keys, self.values())

    @classmethod
    def full_serializer(cls, value, info: core_schema.SerializationInfo):
        ctx = info.context or {}
        should_serialize_redis = ctx.get(REDIS_DUMP_FLAG_NAME)
        return {
            key: cls.serialize_unknown(item) if should_serialize_redis else item
            for key, item in value.items()
        }

    @classmethod
    def full_deserializer(cls, value: dict, info: core_schema.ValidationInfo):
        ctx = info.context or {}
        should_serialize_redis = ctx.get(REDIS_DUMP_FLAG_NAME)
        return {
            key: cls.deserialize_unknown(item) if should_serialize_redis else item
            for key, item in value.items()
        }

    @classmethod
    def schema_for_unknown(cls):
        core_schema.dict_schema(core_schema.str_schema(), core_schema.str_schema())


if TYPE_CHECKING:
    RedisDict: TypeAlias = RedisDict[T] | dict[str, T]  # pragma: no cover
