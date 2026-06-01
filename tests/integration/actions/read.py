import inspect
from abc import ABC
from typing import Any, ClassVar

import pytest

import rapyer
from tests.coverage_helpers import COVER_READ_IN_PIPELINE
from tests.integration.actions.async_action import AsyncActionTestBase


class ReadActionTestBase(AsyncActionTestBase, ABC):
    skip_read_in_pipeline: ClassVar[str | None] = None
    """If set to a reason string, :meth:`test_read_in_pipeline_returns_server_value` is skipped with that reason."""

    def expected_read_output(self) -> Any:
        """Value the read action is expected to return. Defaults to
        :meth:`expected_before`; override when the expected return value
        differs from the pre-action server value (e.g., for pop semantics)."""
        return self.expected_before()

    async def assert_action_effect(self, loaded: Any, action_result: Any):
        """
        For read actions, verify the action's return value matches
        ``expected_read_output``. The model state itself is unchanged for pure
        reads, so checking ``load_data`` is not meaningful here.
        """
        expected = self.expected_read_output()
        assert (
            action_result == expected
        ), f"Action returned {action_result!r}; expected {expected!r}"

    @pytest.mark.asyncio
    async def test_read_in_pipeline_returns_server_value(self, test_input):
        # Arrange
        self.test_input = test_input
        self.created_models = await self.setup_data()

        # Act + Assert
        async with rapyer.apipeline():
            actual = await self.perform_action(self.created_models[0])
            await self.assert_action_effect(self.created_models[0], actual)

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        cls._prepare_action_test(
            test_attr="test_read_in_pipeline_returns_server_value",
            cover_marker=COVER_READ_IN_PIPELINE,
            skip_attr="skip_read_in_pipeline",
            parametrize=True,
        )
