import functools
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

import rapyer
from rapyer import AtomicRedisModel
from rapyer.actions import ActionGroup
from tests.coverage_helpers import (
    COVER_PIPELINE_ATOM,
    COVER_STALE_MIRROR_IN_PIPELINE,
    SPECIAL_FIELD_LIFECYCLE,
    action_groups_for,
    cover_tuple,
    special_field_cover_marker,
)
from tests.integration.special_types.adapters import (
    SPECIAL_FIELD_ADAPTERS,
    SpecialFieldAdapter,
)
from tests.models.pipeline_base import PipelineActionModel


@dataclass
class BinaryOpCase:
    initial: Any
    operand: Any
    expected: Any

    def __str__(self) -> str:
        return f"{self.initial}-{self.operand}-{self.expected}"


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

    skip_special_field_lifecycle: ClassVar[str | None] = None
    skip_special_field_ttl: ClassVar[str | None] = None

    skip_stale_mirror_in_pipeline: ClassVar[str | None] = None
    """If set to a reason string, :meth:`test_action_in_pipeline_tolerates_stale_local_mirror`
    is skipped with that reason. Auto-populated for non-``BaseRedisType`` actions
    (e.g. ``AtomicRedisModel.asave``, ``rapyer.afind``) — those don't operate on
    a field-level local mirror, so the corruption concept doesn't apply."""

    created_models: Any = None
    test_input: Any = None

    @property
    def real_redis_client(self):
        return AtomicRedisModel.Meta.redis

    @abstractmethod
    def create_models(self) -> list[PipelineActionModel]:
        """
        Build (but don't insert) the test models.
        """

    async def setup_data(self) -> list[PipelineActionModel]:
        """
        Default: build models via :meth:`create_models`, insert them, and populate their special fields.
        """
        models = self.create_models()
        async with rapyer.apipeline():
            await rapyer.ainsert(*models)
            await self.populate_special_fields(*models)
        return models

    @abstractmethod
    async def perform_action(self, piped: Any):
        """Perform the mutation inside the pipeline."""

    def corrupt_local_mirror(self, model: PipelineActionModel) -> None:
        """
        Mutate the local Python mirror of the field that ``perform_action``
        targets in a way that would make a native-Python equivalent fail
        (e.g. ``set.discard`` the value before ``aremove``, or clear before
        ``apop``). Subclasses must override unless
        ``skip_stale_mirror_in_pipeline`` is set.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement corrupt_local_mirror "
            f"or set skip_stale_mirror_in_pipeline"
        )

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

    async def assert_after_pipeline(self, loaded: Any):
        expected_after = self.expected_after()
        assert loaded == expected_after, f"Expected {expected_after!r}, got {loaded!r}"

    async def populate_special_fields(self, *models: AtomicRedisModel) -> None:
        """Populate every special field (via each adapter) on each model."""
        for model in models:
            for adapter in SPECIAL_FIELD_ADAPTERS:
                await adapter.populate(model)

    async def create_sp_models(
        self, adapter: SpecialFieldAdapter
    ) -> list[AtomicRedisModel]:
        wrapped = self.create_models()
        self.created_models = wrapped

        async with rapyer.apipeline():
            await rapyer.ainsert(*wrapped)
            for m in wrapped:
                await adapter.populate(m)
        return wrapped

    @pytest.mark.asyncio
    async def _setup_test_special_field_lifecycle_create(
        self, adapter: SpecialFieldAdapter
    ):
        # Arrange
        wrapped = self.create_models()
        self.created_models = wrapped

        # Act
        await self.perform_action(wrapped[0])
        await adapter.populate(wrapped[0])

        # Assert
        await adapter.assert_data_present_by_key(wrapped[0])

    @pytest.mark.asyncio
    async def _setup_test_special_field_lifecycle_delete(
        self, adapter: SpecialFieldAdapter
    ):
        # Arrange
        wrapped = await self.create_sp_models(adapter)

        # Act
        await self.perform_action(wrapped[0])

        # Assert
        for m in wrapped:
            model_exists = await self.real_redis_client.exists(m.key)
            if model_exists:
                continue
            await adapter.assert_data_absent_by_key(m)

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
        await self.assert_after_pipeline(loaded_after)

    @pytest.mark.asyncio
    async def test_action_in_pipeline_tolerates_stale_local_mirror(self, test_input):
        # Arrange - corrupt the local mirror so a native-Python equivalent would fail.
        self.test_input = test_input
        self.created_models = await self.setup_data()
        self.corrupt_local_mirror(self.created_models[0])

        # Act — run inside a pipeline; Redis remains the source of truth.
        async with rapyer.apipeline():
            await self.perform_action(self.created_models[0])

        # Assert - the action still produced the correct Redis state despite the stale mirror.
        loaded_after = await self.load_data()
        await self.assert_after_pipeline(loaded_after)

    @classmethod
    def _prepare_action_test(
        cls,
        *,
        test_attr: str,
        cover_marker: str,
        skip_attr: str,
        parametrize: bool,
        **test_params,
    ):
        """
        Wrap, parametrize, cover-mark and skip-mark one test method on ``cls``.

        Each concrete subclass gets its own fresh function object so pytest
        markers applied here don't leak to sibling subclasses.
        """
        base_fn = getattr(cls, test_attr)

        if parametrize:

            @functools.wraps(base_fn)
            async def wrapped(self, test_input):
                return await base_fn(self, test_input, **test_params)

            params = cls.params or [None]
            wrapped = pytest.mark.parametrize(
                "test_input", params, ids=[repr(p) for p in params]
            )(wrapped)
        else:

            @functools.wraps(base_fn)
            async def wrapped(self):
                return await base_fn(self, **test_params)

        base_sig = inspect.signature(base_fn)
        wrapped.__signature__ = base_sig.replace(
            parameters=[
                p for n, p in base_sig.parameters.items() if n not in test_params
            ]
        )

        methods = cls.covered_method
        if methods is not None:
            if not isinstance(methods, list):
                methods = [methods]
            normalized = [cover_tuple(m) for m in methods]
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
            cover_marker=COVER_PIPELINE_ATOM,
            skip_attr="skip_pipeline_atomicity",
            parametrize=True,
        )
        cls._prepare_action_test(
            test_attr="test_action_in_pipeline_tolerates_stale_local_mirror",
            cover_marker=COVER_STALE_MIRROR_IN_PIPELINE,
            skip_attr="skip_stale_mirror_in_pipeline",
            parametrize=True,
        )
        action_groups = action_groups_for(cls.covered_method)
        if ActionGroup.CREATE in action_groups:
            lifecycle_base_fn = cls._setup_test_special_field_lifecycle_create
        elif ActionGroup.DELETE in action_groups:
            lifecycle_base_fn = cls._setup_test_special_field_lifecycle_delete
        else:
            lifecycle_base_fn = None

        if lifecycle_base_fn is not None:
            for adapter in SPECIAL_FIELD_ADAPTERS:
                test_name = f"test_special_field_lifecycle__{adapter.sf_class.__name__}"
                setattr(cls, test_name, lifecycle_base_fn)
                cls._prepare_action_test(
                    test_attr=test_name,
                    cover_marker=special_field_cover_marker(
                        adapter.sf_class, SPECIAL_FIELD_LIFECYCLE
                    ),
                    skip_attr="skip_special_field_lifecycle",
                    parametrize=False,
                    adapter=adapter,
                )
