import inspect
from abc import ABC
from typing import Any, ClassVar

import pytest

import rapyer
from tests.coverage_helpers import COVER_READ_IN_PIPELINE
from tests.integration.actions.base import ActionTestBase


class ReadActionTestBase(ActionTestBase, ABC):
    skip_read_in_pipeline: ClassVar[str | None] = None
    """If set to a reason string, :meth:`test_read_in_pipeline_returns_server_value`
    is skipped with that reason."""

    @pytest.mark.asyncio
    async def test_read_in_pipeline_returns_server_value(self, test_input):
        # Arrange
        self.test_input = test_input
        self.created_models = await self.setup_data()

        # Act + Assert
        expected = self.expected_before()
        async with rapyer.apipeline():
            actual = await self.perform_action(self.created_models[0])
            assert (
                actual == expected
            ), f"Read action returned {actual!r} inside pipeline; expected {expected!r}"

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
