from datetime import datetime

import pytest

from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SpecialFieldType
from tests.models.collection_types import ComprehensiveTestModel


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


@pytest.mark.asyncio
async def test_comprehensive_model_asave_aget_roundtrip_all_fields_non_default():
    # Arrange
    event_time = datetime(2026, 1, 15, 12, 30, 45)
    event_timestamp = datetime(2025, 6, 1, 9, 0, 0)
    model = ComprehensiveTestModel(
        tags=["alpha", "beta"],
        metadata={"env": "prod", "region": "us-east"},
        name="comprehensive_roundtrip",
        counter=42,
        amount=3.14159,
        data=b"\x00\x01\x02payload",
        event_time=event_time,
        event_timestamp=event_timestamp,
    )
    await model.asave()
    await model.tasks.apush("high", 1.0)
    await model.tasks.apush("medium", 2.0)
    await model.labels.aadd_many({"red", "green", "blue"})

    # Act
    retrieved = await ComprehensiveTestModel.aget(model.key)

    # Assert — round-trip correctness
    assert retrieved == model

    # Assert — no field is at its default value
    default_model = ComprehensiveTestModel()
    for field_name in ComprehensiveTestModel.model_fields:
        retrieved_value = getattr(retrieved, field_name)
        default_value = getattr(default_model, field_name)
        if isinstance(retrieved_value, SpecialFieldType):
            retrieved_data = await extract_sf_data(retrieved_value)
            default_data = await extract_sf_data(default_value)
            assert retrieved_data != default_data, (
                f"SF field {field_name!r} extracted same data as default"
            )
        else:
            assert retrieved_value != default_value, (
                f"Field {field_name!r} is at its default value"
            )
