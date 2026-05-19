from abc import ABC
from datetime import datetime, timedelta

from rapyer.types.datetime import RedisDatetime, RedisDatetimeTimestamp
from tests.integration.actions.base import BinaryOpCase
from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class DatetimeBothModelsOpBase(UpdateActionTestBase, ABC):
    """Datetime iadd/isub tests that mutate both storage flavors at once.

    Setup creates a single :class:`ComprehensiveTestModel` whose ``event_time``
    is a regular datetime (RedisDatetime — ISO storage) and ``event_timestamp``
    is a :class:`RedisDatetimeTimestamp` (numeric storage). Both fields share
    the same initial value.
    """

    def create_models(self):
        initial = self.test_input.initial
        return [ComprehensiveTestModel(event_time=initial, event_timestamp=initial)]

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.event_time, loaded.event_timestamp

    def expected_before(self):
        return self.test_input.initial, self.test_input.initial

    def expected_after(self):
        return self.test_input.expected, self.test_input.expected

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        offset = timedelta(days=999)
        m.event_time += offset
        m.event_timestamp += offset

    def get_target_field(self, m: ComprehensiveTestModel):
        return (m.event_time, m.event_timestamp)


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
