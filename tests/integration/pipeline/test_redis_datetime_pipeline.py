from datetime import datetime, timedelta

import pytest

import rapyer
from tests.models.simple_types import DatetimeModel, DatetimeTimestampModel


@pytest.mark.asyncio
async def test_redis_datetime_timestamp_operations__changes_outside_pipeline_ignored_sanity():
    # Arrange
    initial = datetime(2023, 1, 1, 12, 0, 0)
    model = DatetimeTimestampModel(created_at=initial, updated_at=initial)
    await model.asave()

    # Act - outside pipeline (should be ignored)
    model.created_at += timedelta(days=100)

    # Act - inside pipeline (should take effect)
    async with model.apipeline() as m:
        m.created_at += timedelta(days=1)
        m.created_at += timedelta(microseconds=5)

    # Assert - only pipeline ops applied
    final = await DatetimeTimestampModel.aget(model.key)
    assert final.created_at == datetime(2023, 1, 2, 12, 0, 0, 5)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial", "delta", "expected"],
    [
        [
            datetime(2023, 1, 1, 12, 0, 0),
            timedelta(days=1),
            datetime(2023, 1, 2, 12, 0, 0),
        ],
        [
            datetime(2023, 1, 1, 12, 0, 0),
            timedelta(hours=6),
            datetime(2023, 1, 1, 18, 0, 0),
        ],
        [
            datetime(2023, 12, 31, 23, 0, 0),
            timedelta(hours=2),
            datetime(2024, 1, 1, 1, 0, 0),
        ],
    ],
)
async def test_redis_datetime_iadd_with_pipeline_sanity(initial, delta, expected):
    # Arrange
    model = DatetimeTimestampModel(created_at=initial, updated_at=initial)
    str_date_model = DatetimeModel(created_at=initial, updated_at=initial)
    await rapyer.ainsert(str_date_model, model)

    # Act
    async with model.apipeline() as redis_model:
        redis_model.created_at += delta
        str_date_model.created_at += delta

        # Assert - Change should not be applied yet
        loaded_model = await DatetimeTimestampModel.aget(model.key)
        loaded_str_model = await DatetimeModel.aget(str_date_model.key)
        assert loaded_model.created_at == initial
        assert loaded_str_model.created_at == initial

    # Assert - Change should be applied after pipeline
    final_model = await DatetimeTimestampModel.aget(model.key)
    final_str_model = await DatetimeModel.aget(str_date_model.key)
    assert final_model.created_at == expected
    assert final_str_model.created_at == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial", "delta", "expected"],
    [
        [
            datetime(2023, 1, 2, 12, 0, 0),
            timedelta(days=1),
            datetime(2023, 1, 1, 12, 0, 0),
        ],
        [
            datetime(2023, 1, 1, 18, 0, 0),
            timedelta(hours=6),
            datetime(2023, 1, 1, 12, 0, 0),
        ],
        [
            datetime(2024, 1, 1, 1, 0, 0),
            timedelta(hours=2),
            datetime(2023, 12, 31, 23, 0, 0),
        ],
    ],
)
async def test_redis_datetime_timestamp_isub_with_pipeline_sanity(
    initial, delta, expected
):
    # Arrange
    model = DatetimeTimestampModel(created_at=initial, updated_at=initial)
    str_date_model = DatetimeModel(created_at=initial, updated_at=initial)
    await rapyer.ainsert(str_date_model, model)

    # Act
    async with model.apipeline() as redis_model:
        redis_model.created_at -= delta
        str_date_model.created_at -= delta

        # Assert - Change should not be applied yet
        loaded_model = await DatetimeTimestampModel.aget(model.key)
        loaded_str_model = await DatetimeModel.aget(str_date_model.key)
        assert loaded_model.created_at == initial
        assert loaded_str_model.created_at == initial

    # Assert - Change should be applied after pipeline
    final_model = await DatetimeTimestampModel.aget(model.key)
    final_str_model = await DatetimeModel.aget(str_date_model.key)
    assert final_model.created_at == expected
    assert final_str_model.created_at == expected


@pytest.mark.asyncio
async def test_redis_datetime_operations__all_operations_combined__check_atomicity_sanity():
    # Arrange (regular datetime - ISO string storage)
    initial = datetime(2023, 1, 1, 12, 0, 0)
    model = DatetimeModel(created_at=initial, updated_at=initial)
    await model.asave()

    # Act
    async with model.apipeline() as m:
        m.created_at += timedelta(days=1)
        m.updated_at -= timedelta(hours=6)

        # Assert - changes not visible during pipeline
        loaded = await DatetimeModel.aget(model.key)
        assert loaded.created_at == initial

    # Assert - all changes applied after pipeline
    final = await DatetimeModel.aget(model.key)
    assert final.created_at == datetime(2023, 1, 2, 12, 0, 0)
    assert final.updated_at == datetime(2023, 1, 1, 6, 0, 0)


@pytest.mark.asyncio
async def test_redis_datetime_operations__changes_outside_pipeline_ignored_sanity():
    # Arrange
    initial = datetime(2023, 1, 1, 12, 0, 0)
    model = DatetimeModel(created_at=initial, updated_at=initial)
    await model.asave()

    # Act - outside pipeline (should be ignored)
    model.created_at += timedelta(days=100)

    # Act - inside pipeline (should take effect)
    async with model.apipeline() as m:
        m.created_at += timedelta(hours=3)

    # Assert - only pipeline ops applied
    final = await DatetimeModel.aget(model.key)
    assert final.created_at == datetime(2023, 1, 1, 15, 0, 0)
