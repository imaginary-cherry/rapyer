from datetime import datetime, timezone

import pytest

from tests.models.simple_types import (
    DatetimeModel,
    DatetimeListModel,
    DatetimeDictModel,
)

date_values = [
    datetime(2023, 1, 1, 12, 0, 0),
    datetime(2023, 12, 31, 23, 59, 59),
    datetime(2023, 6, 15, 10, 30, 45, 123456),
    datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
]


@pytest.mark.parametrize("test_values", date_values)
@pytest.mark.asyncio
async def test_redis_datetime_set_functionality_sanity(test_values):
    # Arrange
    model = DatetimeModel()
    await model.asave()

    # Act
    model.created_at = test_values
    await model.created_at.asave()

    # Assert
    fresh_model = DatetimeModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.created_at.aload()
    assert loaded_value == test_values


@pytest.mark.parametrize("test_values", date_values)
@pytest.mark.asyncio
async def test_redis_datetime_load_functionality_sanity(test_values):
    # Arrange
    model = DatetimeModel()
    await model.asave()
    model.created_at = test_values
    await model.created_at.asave()

    # Act
    fresh_model = DatetimeModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.created_at.aload()

    # Assert
    assert loaded_value == test_values


@pytest.mark.asyncio
async def test_redis_datetime_load_with_none_value_edge_case():
    # Arrange
    model = DatetimeModel()

    # Act
    loaded_value = await model.created_at.aload()

    # Assert
    assert loaded_value is None


@pytest.mark.asyncio
async def test_redis_datetime_set_with_wrong_type_edge_case():
    # Arrange
    model = DatetimeModel()

    # Act & Assert
    with pytest.raises(ValueError, match="Input should be a valid datetime"):
        model.created_at = "not a valid datetime"


@pytest.mark.asyncio
async def test_redis_datetime_serialization_functionality_sanity(real_redis_client):
    # Arrange
    test_datetime = datetime(2023, 6, 15, 10, 30, 45, 123456)
    model = DatetimeModel()
    await model.asave()

    # Act
    model.created_at = test_datetime
    await model.created_at.asave()

    # Assert
    raw_value = await real_redis_client.json().get(
        model.key, model.created_at.json_path
    )
    assert raw_value[0] == test_datetime.isoformat()


@pytest.mark.asyncio
async def test_redis_datetime_clone_functionality_sanity():
    # Arrange
    test_datetime = datetime(2023, 1, 1, 12, 0, 0)
    model = DatetimeModel(created_at=test_datetime)

    # Act
    cloned_datetime = model.created_at.clone()

    # Assert
    assert cloned_datetime == test_datetime
    assert not hasattr(cloned_datetime, "key")


@pytest.mark.asyncio
async def test_redis_datetime_persistence_across_instances_edge_case():
    # Arrange
    test_datetime = datetime(2023, 1, 1, 12, 0, 0)
    model1 = DatetimeModel()
    await model1.asave()
    model1.created_at = test_datetime
    await model1.created_at.asave()

    # Act
    model2 = DatetimeModel()
    model2.pk = model1.pk
    loaded_value = await model2.created_at.aload()

    # Assert
    assert loaded_value == test_datetime


@pytest.mark.parametrize(
    "test_dates",
    [
        [datetime(2023, 1, 1), datetime(2023, 6, 15), datetime(2023, 12, 31)],
        [datetime(2023, 1, 1, 12, 30, 45, 123456)],
        [],
    ],
)
@pytest.mark.asyncio
async def test_redis_datetime_list_functionality_sanity(test_dates):
    # Arrange
    model = DatetimeListModel(dates=test_dates)
    await model.asave()

    # Act
    fresh_model = DatetimeListModel()
    fresh_model.pk = model.pk
    loaded_model = await fresh_model.aload()

    # Assert
    assert loaded_model.dates == test_dates


@pytest.mark.parametrize(
    "test_date_dict",
    [
        {"start": datetime(2023, 1, 1), "end": datetime(2023, 12, 31)},
        {"created": datetime(2023, 6, 15, 10, 30, 45, 123456)},
        {},
    ],
)
@pytest.mark.asyncio
async def test_redis_datetime_dict_functionality_sanity(test_date_dict):
    # Arrange
    model = DatetimeDictModel(event_dates=test_date_dict)
    await model.asave()

    # Act
    fresh_model = DatetimeDictModel()
    fresh_model.pk = model.pk
    loaded_model = await fresh_model.aload()

    # Assert
    assert loaded_model.event_dates == test_date_dict


@pytest.mark.asyncio
async def test_redis_datetime_isoformat_compatibility_edge_case(real_redis_client):
    # Arrange
    test_datetime = datetime(2023, 6, 15, 10, 30, 45, 123456)
    model = DatetimeModel()
    await model.asave()

    # Manually set the ISO format string in Redis
    await real_redis_client.json().set(
        model.key, model.created_at.json_path, test_datetime.isoformat()
    )

    # Act
    fresh_model = DatetimeModel()
    fresh_model.pk = model.pk
    loaded_value = await fresh_model.created_at.aload()

    # Assert
    assert loaded_value == test_datetime


@pytest.mark.parametrize("test_datetime", date_values)
@pytest.mark.asyncio
async def test_redis_datetime_model_save_load_sanity(test_datetime):
    # Arrange
    model = DatetimeModel(created_at=test_datetime)
    await model.asave()

    # Act
    loaded_model = await DatetimeModel.aget(model.key)

    # Assert
    assert loaded_model.created_at.timestamp() == test_datetime.timestamp()
    assert loaded_model.updated_at.timestamp() == model.updated_at.timestamp()
