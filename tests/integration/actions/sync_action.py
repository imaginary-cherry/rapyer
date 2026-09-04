import inspect
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pytest

from tests.coverage_helpers import (
    COVER_SYNC_NATIVE_EFFECT,
    COVER_SYNC_NATIVE_RAISES_ON_CORRUPTION,
)
from tests.integration.actions.base import ActionTestBase
from tests.models.pipeline_base import PipelineActionModel


class SyncActionTestBase(ActionTestBase, ABC):
    skip_sync_native_effect: ClassVar[str | None] = None
    skip_sync_native_raises_on_corruption: ClassVar[str | None] = None

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

        # Act - the sync action mutates locally; apply_native_action does the same to the native.
        await self.perform_action(self.created_models[0])
        native_after = self.apply_native_action(native)

        # Assert
        local = self.get_target_field(self.created_models[0])
        assert local == native_after, (
            f"Sync action local effect diverged from native Python equivalent. "
            f"local={local!r}, native={native_after!r}"
        )

    @pytest.mark.asyncio
    async def test_sync_action_native_raises_after_corruption(self, test_input):
        # Arrange — set up data, then corrupt the local mirror.
        self.test_input = test_input
        self.created_models = await self.setup_data()
        self.corrupt_local_mirror(self.created_models[0])

        # Whatever the native equivalent raises on the corrupted copy is what perform_action must.
        native = self.get_target_field(self.created_models[0])
        try:
            self.apply_native_action(native)
        except Exception as native_error:
            expected_error = type(native_error)
        else:
            pytest.fail(
                "apply_native_action did not raise on the corrupted mirror; "
                "the corruption is not a meaningful failure mode for this action."
            )

        # Outside a pipeline the sync action must raise the same type, proving local-only parity.
        with pytest.raises(expected_error):
            await self.perform_action(self.created_models[0])

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
        cls._prepare_action_test(
            test_attr="test_sync_action_native_raises_after_corruption",
            cover_marker=COVER_SYNC_NATIVE_RAISES_ON_CORRUPTION,
            skip_attr="skip_sync_native_raises_on_corruption",
            parametrize=True,
        )
