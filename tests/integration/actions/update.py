import inspect
from abc import ABC
from typing import Any, ClassVar, cast

import pytest

import rapyer
from tests.coverage_helpers import COVER_NO_CLOBBER
from tests.integration.actions.base import ActionTestBase
from tests.models.pipeline_base import INIT_CLOBBER_SENTINEL, PipelineActionModel


class UpdateActionTestBase(ActionTestBase, ABC):
    """Base for actions that modify data in Redis."""

    NO_CLOBBER_SENTINEL_VALUE: ClassVar[str] = "NO_CLOBBER_SENTINEL_42"
    skip_clobber_check: ClassVar[bool] = False
    skip_target_field_clobber_check: ClassVar[str | None] = None

    def local_mutate_target_field(self, model: PipelineActionModel) -> None:
        """Apply a local-only mutation to the field ``perform_action`` targets.

        Subclasses must override this (or set ``skip_target_field_clobber_check``)
        so the no-clobber test can verify that local-only changes don't leak
        into Redis when the pipelined action runs.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement local_mutate_target_field "
            f"or set skip_target_field_clobber_check"
        )

    def get_target_field(self, model: PipelineActionModel) -> Any:
        """Snapshot the target field value (copy, not reference)."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement get_target_field "
            f"or set skip_target_field_clobber_check"
        )

    @pytest.mark.asyncio
    async def test_no_clobber_effect_when_outside_of_pipeline(self, test_input):
        # Arrange
        self.test_input = test_input
        self.created_models = await self.setup_data()
        sentinel_models = self.created_models
        for model in sentinel_models:
            model.pipeline_no_clobber_sentinel = self.NO_CLOBBER_SENTINEL_VALUE

        local_target_value: Any = None
        if not self.skip_target_field_clobber_check:
            self.local_mutate_target_field(self.created_models[0])
            local_target_value = self.get_target_field(self.created_models[0])

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

        if not self.skip_target_field_clobber_check:
            redis_target_value = self.get_target_field(loaded_data[0])
            assert local_target_value != redis_target_value, (
                f"Local-only pre-pipeline mutation on the target field of "
                f"{type(self).__name__} leaked into Redis. "
                f"local={local_target_value!r}, redis={redis_target_value!r}"
            )

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        cls._prepare_action_test(
            test_attr="test_no_clobber_effect_when_outside_of_pipeline",
            cover_marker=COVER_NO_CLOBBER,
            skip_attr="skip_clobber_check",
            parametrize=True,
        )
