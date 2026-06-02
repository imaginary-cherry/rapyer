from rapyer.base import AtomicRedisModel
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SpecialFieldType
from tests.integration.special_types.adapters import SPECIAL_FIELD_ADAPTERS


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


def _adapter_for_field(field: SpecialFieldType):
    for adapter in SPECIAL_FIELD_ADAPTERS:
        if isinstance(field, adapter.sf_class):
            return adapter
    raise NotImplementedError(f"No adapter for SF type {type(field).__name__}")


async def _assert_special_fields_equal(
    actual: AtomicRedisModel, expected: AtomicRedisModel
):
    for field_name in type(actual).model_fields:
        actual_value = getattr(actual, field_name)
        expected_value = getattr(expected, field_name)
        if isinstance(actual_value, SpecialFieldType):
            # Delegate the per-field comparison to its adapter (e.g. the
            # priority queue checks the values stored in Redis).
            await _adapter_for_field(actual_value).assert_field_equal(
                actual_value, expected_value
            )
        elif isinstance(actual_value, AtomicRedisModel):
            # Nested (contained-SF) model: recurse so its special fields are
            # compared too.
            await _assert_special_fields_equal(actual_value, expected_value)


async def assert_atomic_models_equal(
    actual: AtomicRedisModel, expected: AtomicRedisModel
):
    """Assert two models hold the same content, ignoring identity (key/pk)."""
    assert type(actual) is type(
        expected
    ), f"model type differs: {type(actual).__name__} != {type(expected).__name__}"
    assert actual.redis_dump() == expected.redis_dump(), (
        f"JSON payload differs:\n  actual={actual.redis_dump()}\n"
        f"  expected={expected.redis_dump()}"
    )
    await _assert_special_fields_equal(actual, expected)


async def assert_all_round_trip(loaded, originals):
    """Assert ``loaded`` and ``originals`` are equal model-for-model via
    :func:`assert_atomic_models_equal` (same length, pairwise content equal)."""
    assert len(loaded) == len(originals)
    for found, original in zip(loaded, originals):
        await assert_atomic_models_equal(found, original)


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
