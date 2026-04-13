import functools
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

import pytest
import pytest_asyncio

from tests.models.collection_types import ComprehensiveTestModel
from tests.models.functionality_types import AllTypesModel
from tests.models.redis_types import PipelineAllTypesTestModel

# =============================================================================
# Shared case dataclasses
# =============================================================================


@dataclass
class BinaryOpCase:
    initial: Any
    operand: Any
    expected: Any

    def __str__(self) -> str:
        return f"{self.initial}-{self.operand}-{self.expected}"


# =============================================================================
# Base
# =============================================================================


class PipelineAtomicityBase(ABC):
    """
    Abstract base for pipeline-atomicity tests.

    Each ``params`` entry is one dataclass instance — the scaffold stores it on
    ``self.test_input`` before every hook runs, so hooks read
    ``self.test_input.<field>`` directly.
    """

    params: ClassVar[list[Any]] = []
    """Parametrize values — a list of dataclass instances (or ``None`` for no params)."""

    covered_method: ClassVar[Any] = None
    """Method (or list of methods) passed to ``@model_pipeline_test_for``."""

    handle: Any = None
    test_input: Any = None

    @abstractmethod
    async def setup_data(self) -> Any:
        """Create + asave() initial model(s). Return value is stored on ``self.handle``."""

    @abstractmethod
    async def perform_action(self, piped: Any) -> None:
        """Perform the mutation inside the pipeline."""

    @abstractmethod
    async def load_data(self) -> Any:
        """Read state from Redis via ``self.handle``."""

    @abstractmethod
    def expected_before(self) -> Any:
        """Value ``load_data`` should return while the pipeline is still open."""

    @abstractmethod
    def expected_after(self) -> Any:
        """Value ``load_data`` should return after the pipeline exits."""

    def pipeline_owner(self) -> Any:
        """Return the object to call ``.apipeline()`` on. Default: ``self.handle``."""
        return self.handle

    def assert_during_pipeline(self, loaded: Any) -> None:
        assert loaded == self.expected_before()

    def assert_after_pipeline(self, loaded: Any) -> None:
        assert loaded == self.expected_after()

    @pytest_asyncio.fixture(autouse=True)
    async def _capture_real_redis(self, real_redis_client):
        self.real_redis_client = real_redis_client

    @pytest.mark.asyncio
    async def test_pipeline_atomicity(self, test_input) -> None:
        self.test_input = test_input
        self.handle = await self.setup_data()
        owner = self.pipeline_owner()
        async with owner.apipeline() as piped:
            await self.perform_action(piped)
            loaded_during = await self.load_data()
            self.assert_during_pipeline(loaded_during)
        loaded_after = await self.load_data()
        self.assert_after_pipeline(loaded_after)

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        params = cls.params or [None]
        base_fn = cls.test_pipeline_atomicity

        @functools.wraps(base_fn)
        async def test_pipeline_atomicity(self, test_input):
            return await base_fn(self, test_input)

        mark = pytest.mark.parametrize(
            "test_input", params, ids=[repr(p) for p in params]
        )
        cls.test_pipeline_atomicity = mark(test_pipeline_atomicity)


# =============================================================================
# Intermediate bases — shared setup/load per (model, field)
# =============================================================================


class ComprehensiveCounterOpBase(PipelineAtomicityBase, ABC):
    """RedisInt binary ops on ``ComprehensiveTestModel.counter``. ``self.test_input`` is ``BinaryOpCase``."""

    async def setup_data(self):
        model = ComprehensiveTestModel(counter=self.test_input.initial)
        await model.asave()
        return model

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.handle.key)
        return loaded.counter

    def expected_before(self):
        return self.test_input.initial

    def expected_after(self):
        return self.test_input.expected


class PipelineAllTypesAmountOpBase(PipelineAtomicityBase, ABC):
    """RedisFloat binary ops on ``PipelineAllTypesTestModel.amount``. ``self.test_input`` is ``BinaryOpCase``."""

    async def setup_data(self):
        model = PipelineAllTypesTestModel(amount=self.test_input.initial)
        await model.asave()
        return model

    async def load_data(self):
        loaded = await PipelineAllTypesTestModel.aget(self.handle.key)
        return loaded.amount

    def expected_before(self):
        return self.test_input.initial

    def expected_after(self):
        return self.test_input.expected


class PipelineAllTypesNameOpBase(PipelineAtomicityBase, ABC):
    """RedisStr ops on ``PipelineAllTypesTestModel.name``."""

    async def load_data(self):
        loaded = await PipelineAllTypesTestModel.aget(self.handle.key)
        return loaded.name


class ComprehensiveTagsOpBase(PipelineAtomicityBase, ABC):
    """List ops on ``ComprehensiveTestModel.tags``."""

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.handle.key)
        return loaded.tags


class ComprehensiveMetadataOpBase(PipelineAtomicityBase, ABC):
    """Dict ops on ``ComprehensiveTestModel.metadata``."""

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.handle.key)
        return loaded.metadata


class AllTypesModelIntFieldOpBase(PipelineAtomicityBase, ABC):
    """RedisInt ops on ``AllTypesModel.int_field``."""

    async def load_data(self):
        loaded = await AllTypesModel.aget(self.handle.key)
        return loaded.int_field


class AllTypesModelListFieldOpBase(PipelineAtomicityBase, ABC):
    """RedisList ops on ``AllTypesModel.list_field``."""

    async def setup_data(self):
        model = AllTypesModel()
        await model.asave()
        return model

    async def load_data(self):
        loaded = await AllTypesModel.aget(self.handle.key)
        return loaded.list_field

    def expected_before(self):
        return []


class AllTypesModelDictFieldOpBase(PipelineAtomicityBase, ABC):
    """RedisDict ops on ``AllTypesModel.dict_field``."""

    async def setup_data(self):
        model = AllTypesModel()
        await model.asave()
        return model

    async def load_data(self):
        loaded = await AllTypesModel.aget(self.handle.key)
        return loaded.dict_field

    def expected_before(self):
        return {}
