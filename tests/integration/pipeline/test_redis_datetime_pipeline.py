from abc import ABC
from datetime import datetime, timedelta

import pytest

from rapyer.types.datetime import RedisDatetime, RedisDatetimeTimestamp
from tests.integration.pipeline.pipeline_atomicity_base import (
    BinaryOpCase,
    UpdateActionTestBase,
)
from tests.models.collection_types import ComprehensiveTestModel
from tests.models.simple_types import DatetimeModel, DatetimeTimestampModel


class DatetimeBothModelsOpBase(UpdateActionTestBase, ABC):
    """Datetime iadd/isub tests that mutate both storage flavors at once.

    Setup creates a single :class:`ComprehensiveTestModel` whose ``event_time``
    is a regular datetime (RedisDatetime — ISO storage) and ``event_timestamp``
    is a :class:`RedisDatetimeTimestamp` (numeric storage). Both fields share
    the same initial value.
    """

    def create_models(self):
        initial = self.test_input.initial
        return [
            ComprehensiveTestModel(event_time=initial, event_timestamp=initial)
        ]

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.event_time, loaded.event_timestamp

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
        piped.event_time += self.test_input.operand
        piped.event_timestamp += self.test_input.operand


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
        piped.event_time -= self.test_input.operand
        piped.event_timestamp -= self.test_input.operand


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
