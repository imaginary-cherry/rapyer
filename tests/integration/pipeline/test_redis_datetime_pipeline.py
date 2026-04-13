from datetime import datetime, timedelta

import pytest

import rapyer
from rapyer.types.datetime import RedisDatetime, RedisDatetimeTimestamp
from tests.integration.pipeline.pipeline_atomicity_base import PipelineAtomicityBase
from tests.models.simple_types import DatetimeModel, DatetimeTimestampModel


class _DatetimeBothModelsOpBase(PipelineAtomicityBase):
    """Datetime iadd/isub tests that mutate both storage flavors at once.

    Setup creates a :class:`DatetimeTimestampModel` and a :class:`DatetimeModel`
    sharing the same initial ``created_at``. The pipeline is opened on the
    timestamp model; the other model's mutation goes through the same pipeline
    via the context var set by ``apipeline()``.
    """

    param_names = ["initial", "delta", "expected"]

    async def setup_data(self, *, initial, **_):
        ts_model = DatetimeTimestampModel(created_at=initial, updated_at=initial)
        str_date_model = DatetimeModel(created_at=initial, updated_at=initial)
        await rapyer.ainsert(str_date_model, ts_model)
        return ts_model, str_date_model

    def pipeline_owner(self, handle):
        ts_model, _str_date_model = handle
        return ts_model

    async def load_data(self, handle):
        ts_model, str_date_model = handle
        loaded_ts = await DatetimeTimestampModel.aget(ts_model.key)
        loaded_str = await DatetimeModel.aget(str_date_model.key)
        return loaded_ts.created_at, loaded_str.created_at

    def expected_before(self, *, initial, **_):
        return initial, initial

    def expected_after(self, *, expected, **_):
        return expected, expected


class TestRedisDatetimeIadd(_DatetimeBothModelsOpBase):
    covered_method = [RedisDatetime.__iadd__, RedisDatetimeTimestamp.__iadd__]
    params = [
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
    ]

    async def perform_action(self, piped, *, handle, delta, **_):
        _, str_date_model = handle
        piped.created_at += delta
        str_date_model.created_at += delta


class TestRedisDatetimeIsub(_DatetimeBothModelsOpBase):
    covered_method = [RedisDatetime.__isub__, RedisDatetimeTimestamp.__isub__]
    params = [
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
    ]

    async def perform_action(self, piped, *, handle, delta, **_):
        _, str_date_model = handle
        piped.created_at -= delta
        str_date_model.created_at -= delta


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
