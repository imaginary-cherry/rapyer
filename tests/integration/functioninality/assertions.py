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


# Special-field types whose contents must be verified against Redis rather than
# by their in-memory value: their ``__eq__`` is identity/key-scoped (so two
# content-equal instances under different model keys compare unequal) and/or
# they hold no local mirror. For now this is only the priority queue.
REDIS_VERIFIED_SF_TYPES = (RedisPriorityQueue,)


async def _assert_sf_equal(
    path: str, actual: SpecialFieldType, expected: SpecialFieldType
):
    assert type(actual) is type(expected), (
        f"special field {path!r} type differs: "
        f"{type(actual).__name__} != {type(expected).__name__}"
    )
    if isinstance(actual, REDIS_VERIFIED_SF_TYPES):
        # Compare the actual Redis structure, not the (key-scoped) instances.
        actual_data = await extract_sf_data(actual)
        expected_data = await extract_sf_data(expected)
        assert actual_data == expected_data, (
            f"redis-backed special field {path!r} differs: "
            f"{actual_data!r} != {expected_data!r}"
        )
    else:
        assert actual == expected, (
            f"special field {path!r} differs: {actual!r} != {expected!r}"
        )


async def _assert_special_fields_equal(
    actual: AtomicRedisModel, expected: AtomicRedisModel, path: str
):
    for field_name in type(actual).model_fields:
        actual_value = getattr(actual, field_name)
        expected_value = getattr(expected, field_name)
        field_path = f"{path}.{field_name}" if path else field_name
        if isinstance(actual_value, SpecialFieldType):
            await _assert_sf_equal(field_path, actual_value, expected_value)
        elif isinstance(actual_value, AtomicRedisModel):
            # Nested (contained-SF) model: recurse so its special fields are
            # compared too.
            await _assert_special_fields_equal(
                actual_value, expected_value, field_path
            )


async def assert_atomic_models_equal(
    actual: AtomicRedisModel, expected: AtomicRedisModel
):
    """Assert two models hold the same content, ignoring identity (key/pk)."""
    assert type(actual) is type(expected), (
        f"model type differs: {type(actual).__name__} != {type(expected).__name__}"
    )
    assert actual.redis_dump() == expected.redis_dump(), (
        f"JSON payload differs:\n  actual={actual.redis_dump()}\n"
        f"  expected={expected.redis_dump()}"
    )
    await _assert_special_fields_equal(actual, expected, "")


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
