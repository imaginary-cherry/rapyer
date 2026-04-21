import asyncio
import functools
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, cast
from unittest.mock import patch

import pytest
import pytest_asyncio

import rapyer
from rapyer import AtomicRedisModel
from tests.integration.conftest import REDUCED_TTL_SECONDS
from tests.models.collection_types import ComprehensiveTestModel
from tests.models.functionality_types import AllTypesModel
from tests.models.pipeline_base import INIT_CLOBBER_SENTINEL, PipelineActionModel
from tests.models.redis_types import PipelineAllTypesTestModel
from tests.models.simple_types import FloatModel

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
    Define tests for all the actions in this package, so each action will be tested for all the behaviors
    """

    params: ClassVar[list[Any]] = []
    """Parametrize values — a list of dataclass instances (or ``None`` for no params)."""

    covered_method: ClassVar[Any] = None
    """Method (or list of methods) passed to ``@model_pipeline_test_for``."""

    skip_pipeline_atomicity: ClassVar[bool] = False
    """If True, :meth:`test_pipeline_atomicity` is skipped. Use for actions that
    return a value (and so can't be deferred in a pipeline) or that otherwise
    don't have pipeline atomicity coverage."""

    created_models: Any = None
    test_input: Any = None

    @abstractmethod
    def create_models(self) -> list[PipelineActionModel]:
        """
        Build (but don't insert) the test models.
        """

    async def setup_data(self) -> list[PipelineActionModel]:
        """Default: build models via :meth:`create_models` and insert them."""
        models = self.create_models()
        await rapyer.ainsert(*models)
        return models

    @abstractmethod
    async def perform_action(self, piped: Any):
        """Perform the mutation inside the pipeline."""

    async def load_data(self) -> Any:
        """Read state from Redis via ``self.handle``. Default: ``None``."""
        return None

    def expected_before(self) -> Any:
        """Value ``load_data`` should return while the pipeline is still open."""
        return None

    def expected_after(self) -> Any:
        """Value ``load_data`` should return after the pipeline exits."""
        return None

    def assert_during_pipeline(self, loaded: Any):
        assert loaded == self.expected_before()

    def assert_after_pipeline(self, loaded: Any):
        assert loaded == self.expected_after()

    @pytest_asyncio.fixture(autouse=True)
    async def _capture_real_redis(self, real_redis_client):
        self.real_redis_client = real_redis_client

    @pytest.mark.asyncio
    async def test_pipeline_atomicity(self, test_input):
        self.test_input = test_input
        self.created_models = await self.setup_data()
        async with rapyer.apipeline():
            await self.perform_action(self.created_models[0])
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

        methods = cls.covered_method
        if methods is not None:
            if not isinstance(methods, list):
                methods = [methods]
            normalized = []
            for method in methods:
                class_name, method_name = method.__qualname__.rsplit(".", 1)
                normalized.append((class_name, method_name))
            conver_marker = pytest.mark.cover_pipeline_atom(*normalized)
            cls.test_pipeline_atomicity = conver_marker(cls.test_pipeline_atomicity)

        if cls.skip_pipeline_atomicity:
            skip_marker = pytest.mark.skip(
                reason=f"{cls.__name__} has skip_pipeline_atomicity=True"
            )
            cls.test_pipeline_atomicity = skip_marker(cls.test_pipeline_atomicity)


# =============================================================================
# Update action base — pipeline atomicity + no-clobber
# =============================================================================


class UpdateActionTestBase(ActionTestBase, ABC):
    """Base for actions that modify data in Redis.

    Adds :meth:`test_no_clobber`: verifies that performing the action does
    NOT overwrite fields that were changed externally (outside the pipeline).
    """

    NO_CLOBBER_SENTINEL_VALUE: ClassVar[str] = "NO_CLOBBER_SENTINEL_42"

    @pytest.mark.asyncio
    async def test_no_clobber(self, test_input):
        self.test_input = test_input
        self.created_models = await self.setup_data()
        sentinel_models = self.created_models

        # Inject sentinel directly into Redis for every existing model
        for model in sentinel_models:
            model.pipeline_no_clobber_sentinel = self.NO_CLOBBER_SENTINEL_VALUE

        # Perform the action — use pipeline unless the action can't be deferred
        async with rapyer.apipeline():
            await self.perform_action(self.created_models[0])

        # Verify sentinel was NOT overwritten on surviving models
        keys = [model.key for model in sentinel_models]
        loaded_data = await rapyer.afind(*keys)
        loaded_data = cast(list[PipelineActionModel], loaded_data)
        for model in loaded_data:
            sentinel = model.pipeline_no_clobber_sentinel
            assert sentinel == INIT_CLOBBER_SENTINEL, (
                f"pipeline_no_clobber_sentinel on {model.key} was overwritten by "
                f"{type(self).__name__}.perform_action(). "
                f"Expected [{self.NO_CLOBBER_SENTINEL_VALUE!r}], got {sentinel}"
            )

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return

        # Parametrize test_no_clobber (same params as test_pipeline_atomicity)
        params = cls.params or [None]
        base_fn = cls.test_no_clobber

        @functools.wraps(base_fn)
        async def test_no_clobber(self, test_input):
            return await base_fn(self, test_input)

        mark = pytest.mark.parametrize(
            "test_input", params, ids=[repr(p) for p in params]
        )
        cls.test_no_clobber = mark(test_no_clobber)

        # Apply cover_no_clobber marker
        methods = cls.covered_method
        if methods is not None:
            if not isinstance(methods, list):
                methods = [methods]
            normalized = []
            for method in methods:
                class_name, method_name = method.__qualname__.rsplit(".", 1)
                normalized.append((class_name, method_name))
            no_clobber_marker = pytest.mark.cover_no_clobber(*normalized)
            cls.test_no_clobber = no_clobber_marker(cls.test_no_clobber)

        if cls.skip_pipeline_atomicity:
            skip_marker = pytest.mark.skip(
                reason=f"{cls.__name__} has skip_pipeline_atomicity=True"
            )
            cls.test_no_clobber = skip_marker(cls.test_no_clobber)


# =============================================================================
# Async action base — pipeline atomicity + TTL refresh / no-refresh
# =============================================================================


class AsyncActionTestBase(ActionTestBase, ABC):
    """
    Extension of :class:`ActionTestBase` that also exercises TTL refresh
    behavior for async actions decorated with ``@mark_actions``.
    """

    model_exists_before_action: bool = True

    def ttl_keys(self, model: AtomicRedisModel) -> list[str]:
        """Redis keys whose TTL should be asserted. Default: ``[model.key]``.

        Override for actions on special fields to include extra keys such
        as ``model.<field>.special_key``.
        """
        return [model.key]

    async def _setup_ttl_data(self) -> list[AtomicRedisModel]:
        models = await self.setup_data()
        for inst in models:
            for key in self.ttl_keys(inst):
                await self.real_redis_client.expire(key, REDUCED_TTL_SECONDS)
        return models

    @pytest.mark.asyncio
    async def test_ttl_refresh_on_action(self):
        self.created_models = await self._setup_ttl_data()
        model_for_keys = self.created_models[0]

        keys = []
        for model in self.created_models:
            keys.extend(self.ttl_keys(model))
        ttls_before = None
        if self.model_exists_before_action:
            ttls_before: list[int] = await asyncio.gather(
                *[self.real_redis_client.ttl(k) for k in keys]
            )

        with patch("rapyer.base.should_refresh_for_action", return_value=True):
            await self.perform_action(model_for_keys)

        ttl_configured = model_for_keys.Meta.ttl
        afters = await asyncio.gather(
            *[self.real_redis_client.ttl(key) for key in keys]
        )
        if self.model_exists_before_action and ttls_before is not None:
            for key, after, before in zip(keys, afters, ttls_before):
                assert (
                    after > before
                ), f"TTL not refreshed for {key}: before={before} after={after}"

        for key, after in zip(keys, afters):
            assert (
                ttl_configured - 2 < after <= ttl_configured
            ), f"TTL for {key}={after}; expected close to {ttl_configured}"

    @pytest.mark.asyncio
    async def test_ttl_no_refresh_on_action(self):
        self.created_models = await self._setup_ttl_data()
        model_for_keys = self.created_models[0]

        keys = []
        for model in self.created_models:
            keys.extend(self.ttl_keys(model))
        ttls_before = None
        if self.model_exists_before_action:
            ttls_before: list[int] = await asyncio.gather(
                *[self.real_redis_client.ttl(k) for k in keys]
            )

        with patch("rapyer.base.should_refresh_for_action", return_value=False):
            await self.perform_action(model_for_keys)

        afters = await asyncio.gather(
            *[self.real_redis_client.ttl(key) for key in keys]
        )
        if self.model_exists_before_action and ttls_before is not None:
            for key, after, before in zip(keys, afters, ttls_before):
                assert after <= before, (
                    f"TTL unexpectedly refreshed for {key}: before={before} "
                    f"after={after}"
                )
        for key, after in zip(keys, afters):
            assert (
                0 < after <= REDUCED_TTL_SECONDS
            ), f"TTL for {key}={after}; expected in (0, {REDUCED_TTL_SECONDS}]"

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return

        methods = cls.covered_method
        if methods is not None:
            if not isinstance(methods, list):
                methods = [methods]
            normalized = []
            for method in methods:
                class_name, method_name = method.__qualname__.rsplit(".", 1)
                normalized.append((class_name, method_name))

            base_refresh_fn = cls.test_ttl_refresh_on_action

            @functools.wraps(base_refresh_fn)
            async def test_ttl_refresh_on_action(self):
                return await base_refresh_fn(self)

            mark_ttl_test = pytest.mark.cover_ttl_refresh(*normalized)
            cls.test_ttl_refresh_on_action = mark_ttl_test(test_ttl_refresh_on_action)
            base_no_refresh_fn = cls.test_ttl_no_refresh_on_action

            @functools.wraps(base_no_refresh_fn)
            async def test_ttl_no_refresh_on_action(self):
                return await base_no_refresh_fn(self)

            mark_ttl_refresh = pytest.mark.cover_ttl_no_refresh(*normalized)
            cls.test_ttl_no_refresh_on_action = mark_ttl_refresh(
                test_ttl_no_refresh_on_action
            )


# =============================================================================
# Intermediate bases — shared setup/load per (model, field)
# =============================================================================


class ComprehensiveCounterOpBase(UpdateActionTestBase, ABC):
    """RedisInt binary ops on ``ComprehensiveTestModel.counter``. ``self.test_input`` is ``BinaryOpCase``. Sync / pipeline-only."""

    def create_models(self):
        return [ComprehensiveTestModel(counter=self.test_input.initial)]

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.counter

    def expected_before(self):
        return self.test_input.initial

    def expected_after(self):
        return self.test_input.expected


class AsyncComprehensiveCounterOpBase(UpdateActionTestBase, AsyncActionTestBase, ABC):
    """Async ops on ``ComprehensiveTestModel.counter`` (RedisInt) with TTL coverage.

    Parallel to :class:`ComprehensiveCounterOpBase`; used by async mutations
    like ``RedisInt.aincrease`` and field-level ``RedisType.aload`` /
    ``RedisType.asave``.
    """

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.counter


class AsyncFloatModelValueOpBase(UpdateActionTestBase, AsyncActionTestBase, ABC):
    """Async ops on ``FloatModel.value`` (RedisFloat) with TTL coverage."""

    async def load_data(self):
        loaded = await FloatModel.aget(self.created_models[0].key)
        return loaded.value


class AllTypesAmountOpBase(UpdateActionTestBase, ABC):
    """RedisFloat binary ops on ``PipelineAllTypesTestModel.amount``. ``self.test_input`` is ``BinaryOpCase``."""

    def create_models(self):
        return [PipelineAllTypesTestModel(amount=self.test_input.initial)]

    async def load_data(self):
        loaded = await PipelineAllTypesTestModel.aget(self.created_models[0].key)
        return loaded.amount

    def expected_before(self):
        return self.test_input.initial

    def expected_after(self):
        return self.test_input.expected


class AllTypesNameOpBase(UpdateActionTestBase, ABC):
    """RedisStr ops on ``PipelineAllTypesTestModel.name``."""

    async def load_data(self):
        loaded = await PipelineAllTypesTestModel.aget(self.created_models[0].key)
        return loaded.name


class ComprehensiveTagsOpBase(UpdateActionTestBase, ABC):
    """List ops on ``ComprehensiveTestModel.tags``. Sync / pipeline-only actions."""

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.tags


class AsyncComprehensiveTagsOpBase(UpdateActionTestBase, AsyncActionTestBase, ABC):
    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.tags


class ComprehensiveMetadataOpBase(UpdateActionTestBase, ABC):
    """Dict ops on ``ComprehensiveTestModel.metadata``. Sync / pipeline-only."""

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.metadata


class AsyncComprehensiveMetadataOpBase(UpdateActionTestBase, AsyncActionTestBase, ABC):
    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.metadata


class AllTypesModelIntFieldOpBase(UpdateActionTestBase, ABC):
    """RedisInt ops on ``AllTypesModel.int_field``."""

    async def load_data(self):
        loaded = await AllTypesModel.aget(self.created_models[0].key)
        return loaded.int_field


class AllTypesModelListFieldOpBase(UpdateActionTestBase, ABC):
    """RedisList ops on ``AllTypesModel.list_field``."""

    def create_models(self):
        return [AllTypesModel()]

    async def load_data(self):
        loaded = await AllTypesModel.aget(self.created_models[0].key)
        return loaded.list_field

    def expected_before(self):
        return []


class AllTypesModelDictFieldOpBase(UpdateActionTestBase, ABC):
    """RedisDict ops on ``AllTypesModel.dict_field``."""

    def create_models(self):
        return [AllTypesModel()]

    async def load_data(self):
        loaded = await AllTypesModel.aget(self.created_models[0].key)
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

    async def load_data(self):
        model1, model2 = self.created_models
        return (
            await self.real_redis_client.exists(model1.key),
            await self.real_redis_client.exists(model2.key),
        )

    def expected_before(self):
        return 1, 1

    def expected_after(self):
        return 0, 1
