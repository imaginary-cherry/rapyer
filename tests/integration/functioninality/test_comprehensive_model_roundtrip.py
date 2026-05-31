from datetime import datetime

import pytest

import rapyer
from tests.integration.functioninality.assertions import assert_no_field_at_default
from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
async def test_comprehensive_model_asave_aget_roundtrip_all_fields_non_default():
    # Arrange
    event_time = datetime(2026, 1, 15, 12, 30, 45)
    event_timestamp = datetime(2025, 6, 1, 9, 0, 0)
    model = ComprehensiveTestModel(
        pipeline_no_clobber_sentinel="custom_sentinel",
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
    await model.container.labels.aadd_many({"red", "green", "blue"})

    # Act
    retrieved = await ComprehensiveTestModel.aget(model.key)

    # Assert
    assert retrieved == model
    await assert_no_field_at_default(retrieved)


@pytest.mark.asyncio
async def test_comprehensive_model_afind_multiple_keys_all_fields_non_default():
    # Arrange
    model_a = ComprehensiveTestModel(
        pipeline_no_clobber_sentinel="custom_sentinel",
        tags=["alpha", "beta"],
        metadata={"env": "prod", "region": "us-east"},
        name="model_a",
        counter=42,
        amount=3.14159,
        data=b"\x00\x01\x02payload_a",
        event_time=datetime(2026, 1, 15, 12, 30, 45),
        event_timestamp=datetime(2025, 6, 1, 9, 0, 0),
    )
    model_b = ComprehensiveTestModel(
        pipeline_no_clobber_sentinel="custom_sentinel",
        tags=["gamma", "delta"],
        metadata={"tier": "free", "region": "eu-west"},
        name="model_b",
        counter=99,
        amount=2.71828,
        data=b"\xff\xfe\xfdpayload_b",
        event_time=datetime(2024, 11, 30, 23, 59, 59),
        event_timestamp=datetime(2023, 3, 14, 15, 9, 26),
    )
    await model_a.asave()
    await model_b.asave()
    await model_a.tasks.apush("high", 1.0)
    await model_a.tasks.apush("medium", 2.0)
    await model_b.tasks.apush("urgent", 0.1)
    await model_a.container.labels.aadd_many({"red", "green", "blue"})
    await model_b.container.labels.aadd_many({"yellow", "orange"})

    # Act
    retrieved = await rapyer.afind(model_a.key, model_b.key)

    # Assert
    assert len(retrieved) == 2
    assert retrieved[0] == model_a
    assert retrieved[1] == model_b
    for model in retrieved:
        await assert_no_field_at_default(model)
