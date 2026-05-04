import pytest

from rapyer.actions import (
    ActionGroup,
    TargetSource,
    mark_actions,
    register_action_target,
)
from tests.models.simple_types import TTLRefreshTestModel
from tests.unit.mark_actions.conftest import maybe_install_v2

# ---------- target=SELF ----------


@pytest.mark.asyncio
async def test_target_self_registers_first_arg(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def do(model):
        return None

    do = maybe_install_v2(mark_version, do)

    model = TTLRefreshTestModel(name="self-target")

    # Act
    await do(model)

    # Assert
    assert len(refresh_calls) == 1
    assert refresh_calls[0].model is model
    assert refresh_calls[0].action == ActionGroup.UPDATE
    assert refresh_calls[0].initial is False
    assert refresh_calls[0].can_use_pipeline is True


@pytest.mark.asyncio
async def test_target_self_combines_multiple_action_groups(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND, version=mark_version)
    async def append_op(model):
        return None

    append_op = maybe_install_v2(mark_version, append_op)

    model = TTLRefreshTestModel(name="self-combined")

    # Act
    await append_op(model)

    # Assert
    assert len(refresh_calls) == 1
    assert refresh_calls[0].action == ActionGroup.UPDATE | ActionGroup.APPEND


# ---------- target=RESULT ----------


@pytest.mark.asyncio
async def test_target_result_registers_returned_model(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    returned = TTLRefreshTestModel(name="produced")

    @mark_actions(ActionGroup.CREATE, target=TargetSource.RESULT, version=mark_version)
    async def make():
        return returned

    make = maybe_install_v2(mark_version, make)

    # Act
    result = await make()

    # Assert
    assert result is returned
    assert len(refresh_calls) == 1
    assert refresh_calls[0].model is returned
    assert refresh_calls[0].action == ActionGroup.CREATE


@pytest.mark.asyncio
async def test_target_result_registers_each_item_in_list(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    a = TTLRefreshTestModel(name="a")
    b = TTLRefreshTestModel(name="b")

    @mark_actions(ActionGroup.CREATE, target=TargetSource.RESULT, version=mark_version)
    async def make_many():
        return [a, b]

    make_many = maybe_install_v2(mark_version, make_many)

    # Act
    await make_many()

    # Assert
    assert len(refresh_calls) == 2
    refreshed_keys = {c.model.key for c in refresh_calls}
    assert refreshed_keys == {a.key, b.key}


@pytest.mark.asyncio
async def test_target_result_with_tuple_registers_each_item(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    a = TTLRefreshTestModel(name="t1")
    b = TTLRefreshTestModel(name="t2")

    @mark_actions(ActionGroup.CREATE, target=TargetSource.RESULT, version=mark_version)
    async def make_tuple():
        return (a, b)

    make_tuple = maybe_install_v2(mark_version, make_tuple)

    # Act
    await make_tuple()

    # Assert
    assert {c.model.key for c in refresh_calls} == {a.key, b.key}


@pytest.mark.asyncio
async def test_target_result_mixed_list_only_registers_models(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    a = TTLRefreshTestModel(name="mix-a")
    b = TTLRefreshTestModel(name="mix-b")

    @mark_actions(ActionGroup.UPDATE, target=TargetSource.RESULT, version=mark_version)
    async def make_mixed():
        return [a, "junk", 5, b, None]

    make_mixed = maybe_install_v2(mark_version, make_mixed)

    # Act
    await make_mixed()

    # Assert
    refreshed_keys = {c.model.key for c in refresh_calls}
    assert refreshed_keys == {a.key, b.key}


# ---------- target=MANUAL ----------


@pytest.mark.asyncio
async def test_target_manual_does_not_auto_register_first_arg(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    self_model = TTLRefreshTestModel(name="self-skip")
    other_model = TTLRefreshTestModel(name="other-only")

    @mark_actions(ActionGroup.UPDATE, target=TargetSource.MANUAL, version=mark_version)
    async def do(self, other):
        register_action_target(other, ActionGroup.UPDATE)

    do = maybe_install_v2(mark_version, do)

    # Act
    await do(self_model, other_model)

    # Assert: only the manually-registered other was refreshed; self was NOT.
    assert len(refresh_calls) == 1
    assert refresh_calls[0].model is other_model


@pytest.mark.asyncio
async def test_target_manual_with_no_register_calls_skips_refresh(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    self_model = TTLRefreshTestModel(name="manual-skip")

    @mark_actions(ActionGroup.READ, target=TargetSource.MANUAL, version=mark_version)
    async def do(self):
        return None

    do = maybe_install_v2(mark_version, do)

    # Act
    await do(self_model)

    # Assert: nothing was registered, nothing was refreshed.
    assert refresh_calls == []
