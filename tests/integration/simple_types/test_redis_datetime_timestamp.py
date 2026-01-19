from datetime import datetime, timezone

import pytest
from tests.models.simple_types import DatetimeTimestampModel

date_values = [
    datetime(2023, 1, 1, 12, 0, 0),
    datetime(2023, 12, 31, 23, 59, 59),
    datetime(2023, 6, 15, 10, 30, 45, 123456),
    datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
]


@pytest.mark.parametrize("test_values", date_values)
@pytest.mark.asyncio
async def test_redis_datetime_timestamp_set_functionality_sanity(test_values):
    # Arrange
    model = DatetimeTimestampModel()
    await model.asave()

    # Act
    model.created_at = test_values
    await model.created_at.asave()

    # Assert
    fresh_model = DatetimeTimestampModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.created_at.aload()

    # Assert
    assert loaded_value.timestamp() == test_values.timestamp()


@pytest.mark.parametrize("test_values", date_values)
@pytest.mark.asyncio
async def test_redis_datetime_timestamp_load_functionality_sanity(test_values):
    # Arrange
    model = DatetimeTimestampModel()
    await model.asave()
    model.created_at = test_values
    await model.created_at.asave()

    # Act
    fresh_model = DatetimeTimestampModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.created_at.aload()

    # Assert
    assert loaded_value.timestamp() == test_values.timestamp()


@pytest.mark.asyncio
async def test_redis_datetime_timestamp_load_with_none_value_edge_case():
    # Arrange
    model = DatetimeTimestampModel()

    # Act
    loaded_value = await model.created_at.aload()

    # Assert
    assert loaded_value is None


@pytest.mark.asyncio
async def test_redis_datetime_timestamp_set_with_wrong_type_edge_case():
    # Arrange
    model = DatetimeTimestampModel()

    # Act & Assert
    with pytest.raises(ValueError, match="Input should be a valid datetime"):
        model.created_at = "not a valid datetime"


@pytest.mark.asyncio
async def test_redis_datetime_timestamp_serialization_functionality_sanity(
    real_redis_client,
):
    # Arrange
    test_datetime = datetime(2023, 6, 15, 10, 30, 45, 123456)
    model = DatetimeTimestampModel()
    await model.asave()

    # Act
    model.created_at = test_datetime
    await model.created_at.asave()

    # Assert
    raw_value = await real_redis_client.json().get(
        model.key, model.created_at.json_path
    )
    # Should be stored as timestamp (float), not ISO string
    assert raw_value[0] == test_datetime.timestamp()


@pytest.mark.parametrize("test_datetime", date_values)
@pytest.mark.asyncio
async def test_redis_datetime_timestamp_model_save_load_sanity(test_datetime):
    # Arrange
    model = DatetimeTimestampModel(created_at=test_datetime)
    await model.asave()

    # Act
    loaded_model = await DatetimeTimestampModel.aget(model.key)

    # Assert
    loaded_model.created_at = datetime.fromtimestamp(
        loaded_model.created_at.timestamp(), tz=model.created_at.tzinfo
    )
    loaded_model.updated_at = datetime.fromtimestamp(
        loaded_model.updated_at.timestamp(), tz=model.updated_at.tzinfo
    )

    assert loaded_model == model
