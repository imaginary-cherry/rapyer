from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel

T = TypeVar("T")


class ComprehensiveOpBase(UpdateActionTestBase, ABC, Generic[T]):
    """Base for tests that read one field of ``ComprehensiveTestModel``.

    Subclasses implement ``field_getter`` with a typed attribute access, e.g.
    ``return m.amount`` — no string field names.
    """

    @staticmethod
    @abstractmethod
    def field_getter(m: ComprehensiveTestModel) -> T: ...

    async def load_data(self) -> T:
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return type(self).field_getter(loaded)


class ComprehensiveBinaryOpBase(ComprehensiveOpBase[T], ABC, Generic[T]):
    """Base for ``BinaryOpCase`` tests. ``self.test_input`` is ``BinaryOpCase``."""

    @staticmethod
    @abstractmethod
    def make_model(v: T) -> ComprehensiveTestModel: ...

    def create_models(self):
        return [type(self).make_model(self.test_input.initial)]

    def expected_before(self):
        return self.test_input.initial

    def expected_after(self):
        return self.test_input.expected


class ComprehensiveAmountOpBase(ComprehensiveBinaryOpBase[float]):
    """RedisFloat binary ops on ``ComprehensiveTestModel.amount``."""

    @staticmethod
    def field_getter(m: ComprehensiveTestModel) -> float:
        return m.amount

    @staticmethod
    def make_model(v: float) -> ComprehensiveTestModel:
        return ComprehensiveTestModel(amount=v)


class ComprehensiveCounterOpBase(ComprehensiveBinaryOpBase[int]):
    """RedisInt binary ops on ``ComprehensiveTestModel.counter``. Sync / pipeline-only."""

    @staticmethod
    def field_getter(m: ComprehensiveTestModel) -> int:
        return m.counter

    @staticmethod
    def make_model(v: int) -> ComprehensiveTestModel:
        return ComprehensiveTestModel(counter=v)


class ComprehensiveDataOpBase(ComprehensiveOpBase[bytes]):
    """RedisBytes ops on ``ComprehensiveTestModel.data``."""

    @staticmethod
    def field_getter(m: ComprehensiveTestModel) -> bytes:
        return m.data


class ComprehensiveEventTimeOpBase(ComprehensiveOpBase):
    """RedisDatetime ops on ``ComprehensiveTestModel.event_time``."""

    @staticmethod
    def field_getter(m: ComprehensiveTestModel):
        return m.event_time


class ComprehensiveEventTimestampOpBase(ComprehensiveOpBase):
    """RedisDatetimeTimestamp ops on ``ComprehensiveTestModel.event_timestamp``."""

    @staticmethod
    def field_getter(m: ComprehensiveTestModel):
        return m.event_timestamp


class ComprehensiveMetadataOpBase(ComprehensiveOpBase[dict]):
    """Dict ops on ``ComprehensiveTestModel.metadata``. Sync / pipeline-only."""

    @staticmethod
    def field_getter(m: ComprehensiveTestModel) -> dict:
        return m.metadata


class ComprehensiveNameOpBase(ComprehensiveOpBase[str]):
    """RedisStr ops on ``ComprehensiveTestModel.name``."""

    @staticmethod
    def field_getter(m: ComprehensiveTestModel) -> str:
        return m.name


class ComprehensiveTagsOpBase(ComprehensiveOpBase[list]):
    """List ops on ``ComprehensiveTestModel.tags``. Sync / pipeline-only."""

    @staticmethod
    def field_getter(m: ComprehensiveTestModel) -> list:
        return m.tags


class ComprehensiveTasksOpBase(ComprehensiveOpBase):
    """RedisPriorityQueue ops on ``ComprehensiveTestModel.tasks``."""

    @staticmethod
    def field_getter(m: ComprehensiveTestModel):
        return m.tasks
