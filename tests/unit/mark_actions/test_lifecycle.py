import pytest

from rapyer.actions import (
    ActionGroup,
    _action_context,
    mark_actions,
)
from tests.models.simple_types import TTLRefreshTestModel
from tests.unit.mark_actions.conftest import maybe_install_v2


@pytest.mark.asyncio
async def test_action_context_is_none_after_successful_call(
    setup_fake_redis, mark_version
):
    # Arrange
    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def update(m):
        return None

    update = maybe_install_v2(mark_version, update)

    model = TTLRefreshTestModel(name="lifecycle-success")

    assert _action_context.get() is None

    # Act
    await update(model)

    # Assert: outer wrapper resets the contextvar.
    assert _action_context.get() is None


@pytest.mark.asyncio
async def test_exception_inside_wrapped_function_resets_context_and_skips_flush(
    flush_mock, mark_version
):
    # Arrange
    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def boom(m):
        raise RuntimeError("boom")

    boom = maybe_install_v2(mark_version, boom)

    model = TTLRefreshTestModel(name="lifecycle-exception")

    assert _action_context.get() is None

    # Act / Assert: exception propagates out.
    with pytest.raises(RuntimeError, match="boom"):
        await boom(model)

    # Assert: contextvar is reset (finally block) and flush was NOT called
    # (line 189 sits outside the try, so a raise from `await method(...)`
    # bypasses it — current behavior pinned down here).
    assert _action_context.get() is None
    flush_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_args_call_with_target_self_does_not_crash(flush_mock, mark_version):
    # Arrange
    @mark_actions(ActionGroup.READ, version=mark_version)
    async def f():
        return "no-args"

    f = maybe_install_v2(mark_version, f)

    # Act
    result = await f()

    # Assert
    assert result == "no-args"
    flush_mock.assert_awaited_once_with([])


@pytest.mark.asyncio
async def test_flush_raising_still_resets_action_context(flush_mock, mark_version):
    # Arrange
    flush_mock.side_effect = RuntimeError("flush-failed")

    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def update(m):
        return None

    update = maybe_install_v2(mark_version, update)

    model = TTLRefreshTestModel(name="lifecycle-flush-raises")

    assert _action_context.get() is None

    # Act / Assert: the flush error propagates out.
    with pytest.raises(RuntimeError, match="flush-failed"):
        await update(model)

    # Assert: the contextvar was reset by the wrapper's finally block before
    # flush ran, so it's None even though flush blew up.
    assert _action_context.get() is None


@pytest.mark.asyncio
async def test_action_context_does_not_leak_between_independent_calls(
    setup_fake_redis, mark_version
):
    # Arrange
    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def update(m):
        # Inner observation: context IS set during the call.
        assert _action_context.get() is not None

    update = maybe_install_v2(mark_version, update)

    model = TTLRefreshTestModel(name="leak-1")

    # Act / Assert: context is None before, set during, None after — twice.
    assert _action_context.get() is None
    await update(model)
    assert _action_context.get() is None
    await update(model)
    assert _action_context.get() is None
