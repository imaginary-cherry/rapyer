import inspect
from abc import ABC
from typing import Any, ClassVar

import pytest

from tests.coverage_helpers import COVER_ACTION_EFFECT
from tests.integration.actions.base import ActionTestBase


class AsyncActionTestBase(ActionTestBase, ABC):
    """Base for actions that execute against Redis immediately when awaited
    (e.g., ``RedisDict.aupdate``, ``AtomicRedisModel.asave``).

    Adds a sanity check that ``await perform_action(...)`` outside any
    pipeline has the expected effect on the model in Redis.
    """

    skip_action_effect: ClassVar[str | None] = None

    def assert_action_effect(self, loaded: Any, action_result: Any):
        expected_after = self.expected_after()
        assert loaded == expected_after, f"Expected {expected_after!r}, got {loaded!r}"

    @pytest.mark.asyncio
    async def test_async_action_effect(self, test_input):
        # Arrange
        self.test_input = test_input
        self.created_models = await self.setup_data()

        # Act — no pipeline; the awaited async action runs atomically
        action_result = await self.perform_action(self.created_models[0])

        # Assert
        loaded = await self.load_data()
        self.assert_action_effect(loaded, action_result)

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        cls._prepare_action_test(
            test_attr="test_async_action_effect",
            cover_marker=COVER_ACTION_EFFECT,
            skip_attr="skip_action_effect",
            parametrize=True,
        )
