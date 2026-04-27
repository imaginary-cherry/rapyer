from datetime import datetime, timedelta

import pytest

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
