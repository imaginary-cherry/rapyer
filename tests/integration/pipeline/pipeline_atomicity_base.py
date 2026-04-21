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


def _cover_tuple(method: Any) -> tuple[str, str]:
    qualname = method.__qualname__
    if "." in qualname:
        cls_name, method_name = qualname.rsplit(".", 1)
        return cls_name, method_name
    return rapyer.__name__, qualname


class ActionTestBase(ABC):
    """
    Define tests for all the actions in this package, so each action will be tested for all the behaviors
    """

    params: ClassVar[list[Any]] = []
    """Parametrize values — a list of dataclass instances (or ``None`` for no params)."""

    covered_method: ClassVar[Any] = None
    """Method (or list of methods) passed to ``@model_pipeline_test_for``."""

    skip_pipeline_atomicity: ClassVar[str | None] = None
    """If set to a reason string, :meth:`test_pipeline_atomicity` and (when
    applicable) :meth:`test_no_clobber` are skipped with that reason. Use for
    actions that return a value (and so can't be deferred in a pipeline) or
    that otherwise don't have pipeline atomicity coverage."""

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
        # Arrange
        self.test_input = test_input
        self.created_models = await self.setup_data()

        # Act
        async with rapyer.apipeline():
            await self.perform_action(self.created_models[0])
            # Assert (during pipeline)
            loaded_during = await self.load_data()
            self.assert_during_pipeline(loaded_during)

        # Assert (after pipeline)
        loaded_after = await self.load_data()
        self.assert_after_pipeline(loaded_after)

    @classmethod
    def _prepare_action_test(
        cls,
        *,
        test_attr: str,
        cover_marker: str,
        skip_attr: str,
        parametrize: bool,
    ):
        """Wrap, parametrize, cover-mark and skip-mark one test method on ``cls``.

        Each concrete subclass gets its own fresh function object so pytest
        markers applied here don't leak to sibling subclasses.
        """
        base_fn = getattr(cls, test_attr)

        if parametrize:

            @functools.wraps(base_fn)
            async def wrapped(self, test_input):
                return await base_fn(self, test_input)

            params = cls.params or [None]
            wrapped = pytest.mark.parametrize(
                "test_input", params, ids=[repr(p) for p in params]
            )(wrapped)
        else:

            @functools.wraps(base_fn)
            async def wrapped(self):
                return await base_fn(self)

        methods = cls.covered_method
        if methods is not None:
            if not isinstance(methods, list):
                methods = [methods]
            normalized = [_cover_tuple(m) for m in methods]
            wrapped = getattr(pytest.mark, cover_marker)(*normalized)(wrapped)

        skip_reason = getattr(cls, skip_attr)
        if skip_reason:
            wrapped = pytest.mark.skip(reason=skip_reason)(wrapped)

        setattr(cls, test_attr, wrapped)

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        cls._prepare_action_test(
            test_attr="test_pipeline_atomicity",
            cover_marker="cover_pipeline_atom",
            skip_attr="skip_pipeline_atomicity",
            parametrize=True,
        )


# =============================================================================
# Update action base — pipeline atomicity + no-clobber
# =============================================================================


class UpdateActionTestBase(ActionTestBase, ABC):
    """Base for actions that modify data in Redis."""

    NO_CLOBBER_SENTINEL_VALUE: ClassVar[str] = "NO_CLOBBER_SENTINEL_42"

    @pytest.mark.asyncio
    async def test_no_clobber_effect_when_outside_of_pipeline(self, test_input):
        # Arrange
        self.test_input = test_input
        self.created_models = await self.setup_data()
        sentinel_models = self.created_models
        for model in sentinel_models:
            model.pipeline_no_clobber_sentinel = self.NO_CLOBBER_SENTINEL_VALUE

        # Act
        async with rapyer.apipeline():
            await self.perform_action(self.created_models[0])

        # Assert
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
        cls._prepare_action_test(
            test_attr="test_no_clobber_effect_when_outside_of_pipeline",
            cover_marker="cover_no_clobber",
            skip_attr="skip_pipeline_atomicity",
            parametrize=True,
        )


# =============================================================================
# Async action base — pipeline atomicity + TTL refresh / no-refresh
# =============================================================================


class TTLActionTestBase(ActionTestBase, ABC):
    """
    Extension of :class:`ActionTestBase` that also exercises TTL refresh
    behavior for async actions decorated with ``@mark_actions``.
    """

    model_exists_before_action: bool = True

    skip_ttl_refresh: ClassVar[str | None] = None
    """If set to a reason string, :meth:`test_ttl_refresh_on_action` is skipped
    with that reason."""

    skip_ttl_no_refresh: ClassVar[str | None] = None
    """If set to a reason string, :meth:`test_ttl_no_refresh_on_action` is
    skipped with that reason."""

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
        # Arrange
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

        # Act
        with patch("rapyer.base.should_refresh_for_action", return_value=True):
            await self.perform_action(model_for_keys)

        # Assert
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
        # Arrange
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

        # Act
        with patch("rapyer.base.should_refresh_for_action", return_value=False):
            await self.perform_action(model_for_keys)

        # Assert
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
        cls._prepare_action_test(
            test_attr="test_ttl_refresh_on_action",
            cover_marker="cover_ttl_refresh",
            skip_attr="skip_ttl_refresh",
            parametrize=False,
        )
        cls._prepare_action_test(
            test_attr="test_ttl_no_refresh_on_action",
            cover_marker="cover_ttl_no_refresh",
            skip_attr="skip_ttl_no_refresh",
            parametrize=False,
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


class AsyncComprehensiveCounterOpBase(UpdateActionTestBase, TTLActionTestBase, ABC):
    """Async ops on ``ComprehensiveTestModel.counter`` (RedisInt) with TTL coverage.

    Parallel to :class:`ComprehensiveCounterOpBase`; used by async mutations
    like ``RedisInt.aincrease`` and field-level ``RedisType.aload`` /
    ``RedisType.asave``.
    """

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.counter


class AsyncFloatModelValueOpBase(UpdateActionTestBase, TTLActionTestBase, ABC):
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


class AsyncComprehensiveTagsOpBase(UpdateActionTestBase, TTLActionTestBase, ABC):
    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.tags


class ComprehensiveMetadataOpBase(UpdateActionTestBase, ABC):
    """Dict ops on ``ComprehensiveTestModel.metadata``. Sync / pipeline-only."""

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.metadata


class AsyncComprehensiveMetadataOpBase(UpdateActionTestBase, TTLActionTestBase, ABC):
    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.metadata


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


class TwoModelDeleteBase(TTLActionTestBase, ABC):
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
