from abc import ABC
from datetime import datetime, timedelta

import pytest

from rapyer.types.datetime import RedisDatetime, RedisDatetimeTimestamp
from tests.integration.pipeline.pipeline_atomicity_base import (
    BinaryOpCase,
    UpdateActionTestBase,
)
from tests.models.simple_types import DatetimeModel, DatetimeTimestampModel


class DatetimeBothModelsOpBase(UpdateActionTestBase, ABC):
    """Datetime iadd/isub tests that mutate both storage flavors at once.

    Setup creates a :class:`DatetimeTimestampModel` and a :class:`DatetimeModel`
    sharing the same initial ``created_at``. The pipeline is opened on the
    timestamp model; the other model's mutation goes through the same pipeline
    via the context var set by ``apipeline()``.
    """

    def create_models(self):
        initial = self.test_input.initial
        ts_model = DatetimeTimestampModel(created_at=initial, updated_at=initial)
        str_date_model = DatetimeModel(created_at=initial, updated_at=initial)
        return [ts_model, str_date_model]

    def pipeline_owner(self):
        ts_model, _str_date_model = self.created_models
        return ts_model

    async def load_data(self):
        ts_model, str_date_model = self.created_models
        loaded_ts = await DatetimeTimestampModel.aget(ts_model.key)
        loaded_str = await DatetimeModel.aget(str_date_model.key)
        return loaded_ts.created_at, loaded_str.created_at

    def expected_before(self):
        return self.test_input.initial, self.test_input.initial

    def expected_after(self):
        return self.test_input.expected, self.test_input.expected


class TestRedisDatetimeIadd(DatetimeBothModelsOpBase):
    covered_method = [RedisDatetime.__iadd__, RedisDatetimeTimestamp.__iadd__]
    params = [
        BinaryOpCase(
            datetime(2023, 1, 1, 12, 0, 0),
            timedelta(days=1),
            datetime(2023, 1, 2, 12, 0, 0),
        ),
        BinaryOpCase(
            datetime(2023, 1, 1, 12, 0, 0),
            timedelta(hours=6),
            datetime(2023, 1, 1, 18, 0, 0),
        ),
        BinaryOpCase(
            datetime(2023, 12, 31, 23, 0, 0),
            timedelta(hours=2),
            datetime(2024, 1, 1, 1, 0, 0),
        ),
    ]

    async def perform_action(self, piped):
        _, str_date_model = self.created_models
        piped.created_at += self.test_input.operand
        str_date_model.created_at += self.test_input.operand


class TestRedisDatetimeIsub(DatetimeBothModelsOpBase):
    covered_method = [RedisDatetime.__isub__, RedisDatetimeTimestamp.__isub__]
    params = [
        BinaryOpCase(
            datetime(2023, 1, 2, 12, 0, 0),
            timedelta(days=1),
            datetime(2023, 1, 1, 12, 0, 0),
        ),
        BinaryOpCase(
            datetime(2023, 1, 1, 18, 0, 0),
            timedelta(hours=6),
            datetime(2023, 1, 1, 12, 0, 0),
        ),
        BinaryOpCase(
            datetime(2024, 1, 1, 1, 0, 0),
            timedelta(hours=2),
            datetime(2023, 12, 31, 23, 0, 0),
        ),
    ]

    async def perform_action(self, piped):
        _, str_date_model = self.created_models
        piped.created_at -= self.test_input.operand
        str_date_model.created_at -= self.test_input.operand


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
