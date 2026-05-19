from datetime import datetime

import pytest

from tests.models.collection_types import ComprehensiveTestModel


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
    assert retrieved.tags != []
    assert retrieved.metadata != {}
    assert retrieved.name != ""
    assert retrieved.counter != 0
    assert retrieved.amount != 0.0
    assert retrieved.data != b""
    assert retrieved.event_time == event_time
    assert retrieved.event_timestamp == event_timestamp
    assert await retrieved.tasks.asize() > 0
    assert await retrieved.labels.asize() > 0
