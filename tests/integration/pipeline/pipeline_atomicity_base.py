from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pytest
import pytest_asyncio

from tests.models.collection_types import ComprehensiveTestModel
from tests.models.functionality_types import AllTypesModel
from tests.models.redis_types import PipelineAllTypesTestModel


class PipelineAtomicityBase(ABC):
    """
    Abstract base for pipeline-atomicity tests.
    """

    # ---- subclass-overridable knobs -----------------------------------------

    params: ClassVar[list[list[Any]]] = [None]
    """Parametrize cases. Each inner list is one case; empty-inner means 'no params'."""

    covered_method: ClassVar[Any] = None
    """Method (or list of methods) passed to ``@model_pipeline_test_for``."""

    # ---- required hooks -----------------------------------------------------

    @abstractmethod
    async def setup_data(self, **params: Any) -> Any:
        """Create + asave() initial model(s). Return a handle used by later hooks."""

    @abstractmethod
    async def perform_action(self, piped: Any, **params: Any) -> None:
        """Perform the mutation inside the pipeline context.

        ``piped`` is the pipeline-wrapped view returned by ``apipeline()``.
        ``params`` also contains the special ``handle`` key (whatever
        ``setup_data`` returned) for cases where the mutation needs the raw
        handle — e.g. the pipe owner is only one of several models returned.
        """

    @abstractmethod
    async def load_data(self, handle: Any) -> Any:
        """Read the state back from Redis. Called both inside and outside the pipeline."""

    @abstractmethod
    def expected_before(self, **params: Any) -> Any:
        """Value ``load_data`` should return while the pipeline is still open."""

    @abstractmethod
    def expected_after(self, **params: Any) -> Any:
        """Value ``load_data`` should return after the pipeline exits."""

    # ---- optional overrides -------------------------------------------------

    def pipeline_owner(self, handle: Any) -> Any:
        """Return the object to call ``.apipeline()`` on. Default: handle itself.

        Override when ``setup_data`` returns a composite (e.g. a tuple of models)
        where only one of the pieces is a valid pipeline owner.
        """
        return handle

    def assert_during_pipeline(self, loaded: Any, **params: Any) -> None:
        """Verify the in-pipeline read. Default: equality with ``expected_before``."""
        assert loaded == self.expected_before(**params)

    def assert_after_pipeline(self, loaded: Any, **params: Any) -> None:
        """Verify the post-pipeline read. Default: equality with ``expected_after``."""
        assert loaded == self.expected_after(**params)

    # ---- fixtures -----------------------------------------------------------

    @pytest_asyncio.fixture(autouse=True)
    async def _capture_real_redis(self, real_redis_client):
        """Stash the autouse Redis client on ``self`` for hooks that need raw access."""
        self.real_redis_client = real_redis_client

    # ---- scaffold (leaves don't override this) ------------------------------

    async def test_pipeline_atomicity(self, test_input) -> None:
        handle = await self.setup_data(**params)
        owner = self.pipeline_owner(handle)
        async with owner.apipeline() as _piped:
            await self.perform_action(_piped, handle=handle, **params)
            loaded_during = await self.load_data(handle)
            self.assert_during_pipeline(loaded_during, **params)
        loaded_after = await self.load_data(handle)
        self.assert_after_pipeline(loaded_after, **params)

    # ---- wiring -------------------------------------------------------------

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if cls.params:
            ids, vals = zip(*[(c[0], c[1:]) for c in cls.params])
            mark = pytest.mark.parametrize("test_input", vals, ids=ids)
            cls.test_pipeline_atomicity = mark(cls.test_pipeline_atomicity)


# =============================================================================
# Intermediate bases — shared setup/load per (model, field)
# =============================================================================


class ComprehensiveCounterOpBase(PipelineAtomicityBase):
    """RedisInt binary ops on ``ComprehensiveTestModel.counter``."""

    param_names = ["initial_value", "operand", "expected"]

    async def setup_data(self, *, initial_value, **_):
        model = ComprehensiveTestModel(counter=initial_value)
        await model.asave()
        return model

    async def load_data(self, model):
        loaded = await ComprehensiveTestModel.aget(model.key)
        return loaded.counter

    def expected_before(self, *, initial_value, **_):
        return initial_value

    def expected_after(self, *, expected, **_):
        return expected


class PipelineAllTypesAmountOpBase(PipelineAtomicityBase):
    """RedisFloat binary ops on ``PipelineAllTypesTestModel.amount``."""

    param_names = ["initial_value", "operand", "expected"]

    async def setup_data(self, *, initial_value, **_):
        model = PipelineAllTypesTestModel(amount=initial_value)
        await model.asave()
        return model

    async def load_data(self, model):
        loaded = await PipelineAllTypesTestModel.aget(model.key)
        return loaded.amount

    def expected_before(self, *, initial_value, **_):
        return initial_value

    def expected_after(self, *, expected, **_):
        return expected


class PipelineAllTypesNameOpBase(PipelineAtomicityBase):
    """RedisStr ops on ``PipelineAllTypesTestModel.name``."""

    async def load_data(self, model):
        loaded = await PipelineAllTypesTestModel.aget(model.key)
        return loaded.name


class ComprehensiveTagsOpBase(PipelineAtomicityBase):
    """List ops on ``ComprehensiveTestModel.tags``."""

    async def load_data(self, model):
        loaded = await ComprehensiveTestModel.aget(model.key)
        return loaded.tags


class ComprehensiveMetadataOpBase(PipelineAtomicityBase):
    """Dict ops on ``ComprehensiveTestModel.metadata``."""

    async def load_data(self, model):
        loaded = await ComprehensiveTestModel.aget(model.key)
        return loaded.metadata


class AllTypesModelIntFieldOpBase(PipelineAtomicityBase):
    """RedisInt ops on ``AllTypesModel.int_field``."""

    async def load_data(self, model):
        loaded = await AllTypesModel.aget(model.key)
        return loaded.int_field


class AllTypesModelListFieldOpBase(PipelineAtomicityBase):
    """RedisList ops on ``AllTypesModel.list_field``."""

    async def setup_data(self, **_):
        model = AllTypesModel()
        await model.asave()
        return model

    async def load_data(self, model):
        loaded = await AllTypesModel.aget(model.key)
        return loaded.list_field

    def expected_before(self, **_):
        return []


class AllTypesModelDictFieldOpBase(PipelineAtomicityBase):
    """RedisDict ops on ``AllTypesModel.dict_field``."""

    async def setup_data(self, **_):
        model = AllTypesModel()
        await model.asave()
        return model

    async def load_data(self, model):
        loaded = await AllTypesModel.aget(model.key)
        return loaded.dict_field

    def expected_before(self, **_):
        return {}
