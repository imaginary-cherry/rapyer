import asyncio
import inspect
from abc import ABC
from dataclasses import dataclass
from typing import Any, ClassVar
from unittest.mock import patch

import pytest

from tests.coverage_helpers import COVER_NO_TTL_WHEN_NOT_CONFIGURED
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.special_types.adapters import SPECIAL_FIELD_ADAPTERS
from tests.models.collection_types import ComprehensiveTestModel


@dataclass
class SpecialFieldCase:
    """
    One parametrization case for a create-action test: whether the model's
    special fields are assigned data at construction.
    """

    assigned_sf: bool

    def __repr__(self) -> str:
        # Used by pytest.mark.parametrize ids (the framework calls repr).
        return "sf-assigned" if self.assigned_sf else "sf-empty"


def _assign_at_path(model: ComprehensiveTestModel, path: tuple[str, ...], value):
    """
    Assign ``value`` at the nested attribute ``path`` (e.g.
    ``("container", "labels")``). Special fields re-link to their parent on
    assignment, so ``special_key`` resolves correctly.
    """
    obj = model
    for segment in path[:-1]:
        obj = getattr(obj, segment)
    setattr(obj, path[-1], value)


class CreateActionTestBase(TTLActionTestBase, ABC):
    """Class for action that create models"""

    skip_no_ttl_when_not_configured: ClassVar[str | None] = None

    params = [SpecialFieldCase(assigned_sf=True), SpecialFieldCase(assigned_sf=False)]

    def _assigned_sf(self) -> bool:
        # Non-parametrized tests run with test_input=None and never assert SF round-trip.
        return getattr(self.test_input, "assigned_sf", True)

    def build_model(self, **kwargs) -> ComprehensiveTestModel:
        model = ComprehensiveTestModel(**kwargs)
        if self._assigned_sf():
            for adapter in SPECIAL_FIELD_ADAPTERS:
                for path, value in adapter.in_memory_assignments():
                    _assign_at_path(model, path, value)
        return model

    async def populate_special_fields(self, *models):
        # SF is assigned in-memory at construction; do not pre-write to Redis.
        return

    async def setup_for_creation(self):
        return self.create_models()

    @pytest.mark.asyncio
    async def test_no_ttl_set_when_ttl_not_configured(self):
        # Arrange - resolve the class without persisting, so the patch can wrap any pre-inserts.
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
