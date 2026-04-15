import functools
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

import pytest
import pytest_asyncio

import rapyer
from rapyer import AtomicRedisModel
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


class ActionTestBase(ABC):
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
    def create_models(self) -> list[AtomicRedisModel] | AtomicRedisModel:
        """
        Build (but don't insert) the test models.
        """

    async def setup_data(self) -> Any:
        """Default: build models via :meth:`create_models` and insert them."""
        models = self.create_models()
        to_insert = models if isinstance(models, list) else [models]
        await rapyer.ainsert(*to_insert)
        return models

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


class RapyerPipelineBase(ActionTestBase, ABC):
    """Atomicity via the module-level ``rapyer.apipeline()`` context."""

    def pipeline_owner(self):
        return rapyer


class ComprehensiveCounterOpBase(ActionTestBase, ABC):
    """RedisInt binary ops on ``ComprehensiveTestModel.counter``. ``self.test_input`` is ``BinaryOpCase``."""

    def create_models(self):
        return ComprehensiveTestModel(counter=self.test_input.initial)

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.handle.key)
        return loaded.counter

    def expected_before(self):
        return self.test_input.initial

    def expected_after(self):
        return self.test_input.expected


class PipelineAllTypesAmountOpBase(ActionTestBase, ABC):
    """RedisFloat binary ops on ``PipelineAllTypesTestModel.amount``. ``self.test_input`` is ``BinaryOpCase``."""

    def create_models(self):
        return PipelineAllTypesTestModel(amount=self.test_input.initial)

    async def load_data(self):
        loaded = await PipelineAllTypesTestModel.aget(self.handle.key)
        return loaded.amount

    def expected_before(self):
        return self.test_input.initial

    def expected_after(self):
        return self.test_input.expected


class PipelineAllTypesNameOpBase(ActionTestBase, ABC):
    """RedisStr ops on ``PipelineAllTypesTestModel.name``."""

    async def load_data(self):
        loaded = await PipelineAllTypesTestModel.aget(self.handle.key)
        return loaded.name


class ComprehensiveTagsOpBase(ActionTestBase, ABC):
    """List ops on ``ComprehensiveTestModel.tags``."""

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.handle.key)
        return loaded.tags


class ComprehensiveMetadataOpBase(ActionTestBase, ABC):
    """Dict ops on ``ComprehensiveTestModel.metadata``."""

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.handle.key)
        return loaded.metadata


class AllTypesModelIntFieldOpBase(ActionTestBase, ABC):
    """RedisInt ops on ``AllTypesModel.int_field``."""

    async def load_data(self):
        loaded = await AllTypesModel.aget(self.handle.key)
        return loaded.int_field


class AllTypesModelListFieldOpBase(ActionTestBase, ABC):
    """RedisList ops on ``AllTypesModel.list_field``."""

    def create_models(self):
        return AllTypesModel()

    async def load_data(self):
        loaded = await AllTypesModel.aget(self.handle.key)
        return loaded.list_field

    def expected_before(self):
        return []


class AllTypesModelDictFieldOpBase(ActionTestBase, ABC):
    """RedisDict ops on ``AllTypesModel.dict_field``."""

    def create_models(self):
        return AllTypesModel()

    async def load_data(self):
        loaded = await AllTypesModel.aget(self.handle.key)
        return loaded.dict_field

    def expected_before(self):
        return {}


class TwoModelDeleteBase(ActionTestBase, ABC):
    """Two-model delete atomicity: model1 deleted, model2 preserved."""

    def create_models(self):
        return [
            ComprehensiveTestModel(tags=["tag1"], name="model1"),
            ComprehensiveTestModel(tags=["tag2"], name="model2"),
        ]

    def pipeline_owner(self):
        return self.handle[0]

    async def load_data(self):
        model1, model2 = self.handle
        return (
            await self.real_redis_client.exists(model1.key),
            await self.real_redis_client.exists(model2.key),
        )

    def expected_before(self):
        return 1, 1

    def expected_after(self):
        return 0, 1
