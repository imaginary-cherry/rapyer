import inspect
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pytest

from tests.coverage_helpers import COVER_SYNC_NATIVE_EFFECT
from tests.integration.actions.base import ActionTestBase
from tests.models.pipeline_base import PipelineActionModel


class SyncActionTestBase(ActionTestBase, ABC):
    skip_sync_native_effect: ClassVar[str | None] = None

    @abstractmethod
    def get_target_field(self, model: PipelineActionModel) -> Any:
        """Return a native-Python copy of the field's current local state."""

    @abstractmethod
    def apply_native_action(self, native: Any) -> Any:
        """
        Apply, on a plain Python object, the same operation that
        ``perform_action`` performs on the field. Return the resulting value
        (mutated ``native`` for in-place ops; a new object for immutable types).
        """

    @pytest.mark.asyncio
    async def test_sync_action_local_effect_matches_native_python(self, test_input):
        # Arrange
        self.test_input = test_input
        self.created_models = await self.setup_data()
        native = self.get_target_field(self.created_models[0])

        # Act — sync action mutates the redis-backed field locally;
        # apply_native_action does the equivalent on the native object.
        await self.perform_action(self.created_models[0])
        native_after = self.apply_native_action(native)

        # Assert
        local = self.get_target_field(self.created_models[0])
        assert local == native_after, (
            f"Sync action local effect diverged from native Python equivalent. "
            f"local={local!r}, native={native_after!r}"
        )

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        cls._prepare_action_test(
            test_attr="test_sync_action_local_effect_matches_native_python",
            cover_marker=COVER_SYNC_NATIVE_EFFECT,
            skip_attr="skip_sync_native_effect",
            parametrize=True,
        )
