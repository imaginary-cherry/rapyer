from rapyer.base import AtomicRedisModel
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SpecialFieldType


async def _extract_redis_set(field: RedisSet):
    return await field.amembers()


async def _extract_redis_priority_queue(field: RedisPriorityQueue):
    return await field.aitems()


_SF_EXTRACTORS = {
    RedisSet: _extract_redis_set,
    RedisPriorityQueue: _extract_redis_priority_queue,
}


async def extract_sf_data(field: SpecialFieldType):
    for sf_type, extractor in _SF_EXTRACTORS.items():
        if isinstance(field, sf_type):
            return await extractor(field)
    raise NotImplementedError(f"No extractor for SF type {type(field).__name__}")


async def assert_no_field_at_default(model_instance: AtomicRedisModel):
    default_model = type(model_instance)()
    for field_name in type(model_instance).model_fields:
        value = getattr(model_instance, field_name)
        default_value = getattr(default_model, field_name)
        if isinstance(value, SpecialFieldType):
            value_data = await extract_sf_data(value)
            default_data = await extract_sf_data(default_value)
            assert (
                value_data != default_data
            ), f"SF field {field_name!r} extracted same data as default"
        elif isinstance(value, AtomicRedisModel):
            # Nested container model: recurse so its (possibly special) fields
            # are checked by value rather than by trivially-distinct identity.
            await assert_no_field_at_default(value)
        else:
            assert (
                value != default_value
            ), f"Field {field_name!r} is at its default value"
