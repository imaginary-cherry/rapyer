import asyncio
import inspect
from abc import ABC
from typing import Any, ClassVar
from unittest.mock import patch

import pytest

from tests.coverage_helpers import COVER_NO_TTL_WHEN_NOT_CONFIGURED
from tests.integration.actions.ttl import TTLActionTestBase


class CreateActionTestBase(TTLActionTestBase, ABC):
    """Class for action that create models"""

    skip_no_ttl_when_not_configured: ClassVar[str | None] = None

    async def setup_for_creation(self):
        return self.create_models()

    @pytest.mark.asyncio
    async def test_no_ttl_set_when_ttl_not_configured(self):
        # Arrange
        # Determine the model class without persisting anything so the
        # patch can wrap any pre-inserts in ``setup_for_creation``.
        model_cls = type(self.create_models()[0])

        # Act
        with patch.object(model_cls.Meta, "ttl", None):
            self.created_models = await self.setup_for_creation()
            await self.perform_action(self.created_models[0])

        # Assert
        keys = self.all_keys_to_check()
        ttls = await asyncio.gather(*[self.real_redis_client.ttl(k) for k in keys])
        for key, ttl in zip(keys, ttls):
            assert ttl == -1, f"TTL unexpectedly set for {key}: expected -1, got {ttl}"

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        cls._prepare_action_test(
            test_attr="test_no_ttl_set_when_ttl_not_configured",
            cover_marker=COVER_NO_TTL_WHEN_NOT_CONFIGURED,
            skip_attr="skip_no_ttl_when_not_configured",
            parametrize=False,
        )
