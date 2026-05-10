import pytest

from rapyer.actions import (
    ActionGroup,
    TargetSource,
    mark_actions,
    register_action_target,
)
from tests.models.simple_types import TTLRefreshTestModel
from tests.unit.mark_actions.conftest import maybe_install_v2


@pytest.mark.asyncio
async def test_flush_refreshes_all_registered_models_including_inner_calls(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    @mark_actions(ActionGroup.UPDATE, target=TargetSource.MANUAL, version=mark_version)
    async def _inner_register(model):
        register_action_target(model, ActionGroup.UPDATE)

    @mark_actions(ActionGroup.UPDATE, target=TargetSource.MANUAL, version=mark_version)
    async def _outer_register(outer_model, inner_model):
        register_action_target(outer_model, ActionGroup.UPDATE)
        await _inner_register(inner_model)

    _inner_register, _outer_register = maybe_install_v2(
        mark_version, _inner_register, _outer_register
    )

    a = TTLRefreshTestModel(name="flush-outer")
    b = TTLRefreshTestModel(name="flush-inner")

    # Act
    await _outer_register(a, b)

    # Assert
    refreshed_keys = {c.model.key for c in refresh_calls}
    assert refreshed_keys == {a.key, b.key}


@pytest.mark.asyncio
async def test_flush_refreshes_single_model_via_target_self(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def update(m):
        return None

    update = maybe_install_v2(mark_version, update)

    model = TTLRefreshTestModel(name="flush-self")

    # Act
    await update(model)

    # Assert
    assert len(refresh_calls) == 1
    assert refresh_calls[0].model is model
