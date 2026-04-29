from unittest.mock import AsyncMock

import pytest

import rapyer.actions
from rapyer.actions import (
    ActionGroup,
    _action_context,
    mark_actions,
)
from tests.models.simple_types import TTLRefreshTestModel


@pytest.mark.asyncio
async def test_action_context_is_none_after_successful_call(setup_fake_redis):
    # Arrange
    @mark_actions(ActionGroup.UPDATE)
    async def update(m):
        return None

    model = TTLRefreshTestModel(name="lifecycle-success")

    assert _action_context.get() is None

    # Act
    await update(model)

    # Assert: outer wrapper resets the contextvar.
    assert _action_context.get() is None


@pytest.mark.asyncio
async def test_exception_inside_wrapped_function_resets_context_and_skips_flush(
    monkeypatch,
):
    # Arrange
    flush_mock = AsyncMock()
    monkeypatch.setattr(rapyer.actions, "flush_action_targets", flush_mock)

    @mark_actions(ActionGroup.UPDATE)
    async def boom(m):
        raise RuntimeError("boom")

    model = TTLRefreshTestModel(name="lifecycle-exception")

    assert _action_context.get() is None

    # Act / Assert: exception propagates out.
    with pytest.raises(RuntimeError, match="boom"):
        await boom(model)

    # Assert: contextvar is reset (finally block) and flush was NOT called
    # (line 189 sits outside the try, so a raise from `await method(...)`
    # bypasses it — current behavior pinned down here).
    assert _action_context.get() is None
    assert flush_mock.await_count == 0


@pytest.mark.asyncio
async def test_target_self_with_non_registerable_first_arg_does_not_crash(
    monkeypatch,
):
    # Arrange
    flush_mock = AsyncMock()
    monkeypatch.setattr(rapyer.actions, "flush_action_targets", flush_mock)

    @mark_actions(ActionGroup.READ)
    async def f(x):
        return x

    # Act
    result = await f(42)

    # Assert
    assert result == 42
    assert flush_mock.await_count == 1
    (targets,), _ = flush_mock.call_args
    assert targets == []


@pytest.mark.asyncio
async def test_no_args_call_with_target_self_does_not_crash(monkeypatch):
    # Arrange
    flush_mock = AsyncMock()
    monkeypatch.setattr(rapyer.actions, "flush_action_targets", flush_mock)

    @mark_actions(ActionGroup.READ)
    async def f():
        return "no-args"

    # Act
    result = await f()

    # Assert
    assert result == "no-args"
    assert flush_mock.await_count == 1


@pytest.mark.asyncio
async def test_action_context_does_not_leak_between_independent_calls(
    setup_fake_redis,
):
    # Arrange
    @mark_actions(ActionGroup.UPDATE)
    async def update(m):
        # Inner observation: context IS set during the call.
        assert _action_context.get() is not None

    model = TTLRefreshTestModel(name="leak-1")

    # Act / Assert: context is None before, set during, None after — twice.
    assert _action_context.get() is None
    await update(model)
    assert _action_context.get() is None
    await update(model)
    assert _action_context.get() is None
