from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.exceptions import NoScriptError

from rapyer.context import execute_pipeline_with_noscript_recovery
from rapyer.errors import PersistentNoScriptError


def _make_pipe(command_stack, execute_side_effect):
    pipe = MagicMock()
    pipe.command_stack = command_stack
    pipe.execute = AsyncMock(side_effect=execute_side_effect)
    return pipe


def _make_meta_with_retry_pipe(retry_pipe):
    meta = MagicMock()

    class _RetryPipeContext:
        async def __aenter__(self_inner):
            return retry_pipe

        async def __aexit__(self_inner, *exc_info):
            return False

    meta.redis.pipeline = MagicMock(return_value=_RetryPipeContext())
    meta.redis.script_load = AsyncMock(return_value="new_sha")
    return meta


@pytest.mark.asyncio
async def test_execute_pipeline_with_noscript_recovery_returns_result_on_success_sanity():
    # Success path MUST be behaviorally identical to a bare `await pipe.execute()`
    # -- same return value, no extra calls -- so COMPAT-01 stays intact.
    pipe = _make_pipe(
        command_stack=[(("EVALSHA", "sha1", 1, "key"), {})],
        execute_side_effect=[["ok"]],
    )
    meta = MagicMock()

    result = await execute_pipeline_with_noscript_recovery(pipe, meta)

    assert result == ["ok"]
    pipe.execute.assert_awaited_once()
    meta.redis.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_execute_pipeline_with_noscript_recovery_replays_full_command_stack_on_noscript(
    monkeypatch,
):
    # RED: the cascade EVALSHA rides the SAME pipeline as a ride-along
    # JSON.SET (e.g. from asave()). An EVALSHA-only replay would silently
    # drop the JSON.SET. Assert the retry pipe receives BOTH commands, in
    # order, exactly as originally enqueued.
    command_stack = [
        (("JSON.SET", "Model:abc", "$", "{}"), {}),
        (("EVALSHA", "sha1", 1, "Model:abc"), {}),
    ]
    pipe = _make_pipe(command_stack=command_stack, execute_side_effect=NoScriptError())

    retry_pipe = MagicMock()
    retry_pipe.execute = AsyncMock(return_value=[True, [0, 0]])
    meta = _make_meta_with_retry_pipe(retry_pipe)

    handle_noscript_error = AsyncMock()
    monkeypatch.setattr(
        "rapyer.scripts.registry.handle_noscript_error", handle_noscript_error
    )

    result = await execute_pipeline_with_noscript_recovery(pipe, meta)

    handle_noscript_error.assert_awaited_once_with(meta.redis, meta)
    assert retry_pipe.execute_command.call_args_list == [
        (("JSON.SET", "Model:abc", "$", "{}"), {}),
        (("EVALSHA", "sha1", 1, "Model:abc"), {}),
    ]
    retry_pipe.execute.assert_awaited_once()
    assert result == [True, [0, 0]]


@pytest.mark.asyncio
async def test_execute_pipeline_with_noscript_recovery_raises_persistent_on_second_failure(
    monkeypatch,
):
    command_stack = [(("EVALSHA", "sha1", 1, "key"), {})]
    pipe = _make_pipe(command_stack=command_stack, execute_side_effect=NoScriptError())

    retry_pipe = MagicMock()
    retry_pipe.execute = AsyncMock(side_effect=NoScriptError())
    meta = _make_meta_with_retry_pipe(retry_pipe)

    handle_noscript_error = AsyncMock()
    monkeypatch.setattr(
        "rapyer.scripts.registry.handle_noscript_error", handle_noscript_error
    )

    with pytest.raises(PersistentNoScriptError):
        await execute_pipeline_with_noscript_recovery(pipe, meta)
