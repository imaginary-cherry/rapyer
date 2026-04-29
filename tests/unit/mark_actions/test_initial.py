import pytest

from rapyer.actions import (
    ActionGroup,
    TargetSource,
    mark_actions,
    register_action_target,
)
from tests.models.simple_types import TTLRefreshTestModel


@pytest.mark.asyncio
async def test_initial_true_propagates_to_refresh(setup_fake_redis, refresh_calls):
    # Arrange
    @mark_actions(ActionGroup.CREATE, initial=True)
    async def create(model):
        return None

    model = TTLRefreshTestModel(name="initial-direct")

    # Act
    await create(model)

    # Assert
    assert len(refresh_calls) == 1
    assert refresh_calls[0]["initial"] is True


@pytest.mark.asyncio
async def test_initial_false_default_propagates_as_false(
    setup_fake_redis, refresh_calls
):
    # Arrange
    @mark_actions(ActionGroup.UPDATE)
    async def update(model):
        return None

    model = TTLRefreshTestModel(name="initial-default-false")

    # Act
    await update(model)

    # Assert
    assert refresh_calls[0]["initial"] is False


@pytest.mark.asyncio
async def test_nested_outer_initial_true_inner_false_merges_to_true(
    setup_fake_redis, refresh_calls
):
    # Arrange
    model = TTLRefreshTestModel(name="merge-outer-true")

    @mark_actions(ActionGroup.UPDATE)
    async def inner(m):
        return None

    @mark_actions(ActionGroup.CREATE, initial=True)
    async def outer(m):
        await inner(m)

    # Act
    await outer(model)

    # Assert: deduplicated to a single refresh, initial OR-merged to True.
    assert len(refresh_calls) == 1
    assert refresh_calls[0]["model"] is model
    assert refresh_calls[0]["initial"] is True
    assert refresh_calls[0]["action"] == ActionGroup.CREATE | ActionGroup.UPDATE


@pytest.mark.asyncio
async def test_nested_outer_initial_false_inner_true_merges_to_true(
    setup_fake_redis, refresh_calls
):
    # Arrange
    model = TTLRefreshTestModel(name="merge-inner-true")

    @mark_actions(ActionGroup.CREATE, initial=True)
    async def inner(m):
        return None

    @mark_actions(ActionGroup.UPDATE)
    async def outer(m):
        await inner(m)

    # Act
    await outer(model)

    # Assert: order doesn't matter — initial flag still propagates as True.
    assert len(refresh_calls) == 1
    assert refresh_calls[0]["initial"] is True


@pytest.mark.asyncio
async def test_two_models_initial_flag_per_model(setup_fake_redis, refresh_calls):
    """In one flush, distinct models keep their own initial flags."""
    # Arrange
    creating = TTLRefreshTestModel(name="creating-model")
    updating = TTLRefreshTestModel(name="updating-model")

    @mark_actions(ActionGroup.CREATE, initial=True)
    async def create_one(m):
        return None

    @mark_actions(ActionGroup.UPDATE, target=TargetSource.MANUAL)
    async def parent(creating_model, updating_model):
        # Outer registers updating_model with initial=False (target=MANUAL with explicit
        # register call below would carry the initial we pass; here the outer marks
        # updating_model itself by calling the inner create on the other.
        await create_one(creating_model)

        register_action_target(updating_model, ActionGroup.UPDATE)

    # Act
    await parent(creating, updating)

    # Assert
    by_model = {id(c["model"]): c for c in refresh_calls}
    assert by_model[id(creating)]["initial"] is True
    assert by_model[id(updating)]["initial"] is False
