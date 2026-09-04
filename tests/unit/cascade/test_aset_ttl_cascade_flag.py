import inspect
from unittest.mock import AsyncMock, patch

import pytest

from rapyer.base import AtomicRedisModel
from rapyer.result import CascadeResult
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import CascadeChainNode, CascadeChainRoot

TTL_SECONDS = 120


def test_aset_ttl_signature_has_cascade_kwarg_defaulting_false():
    # Act
    sig = inspect.signature(AtomicRedisModel.aset_ttl)

    # Assert
    assert "cascade" in sig.parameters
    assert sig.parameters["cascade"].default is False


@pytest.mark.asyncio
async def test_aset_ttl_default_cascade_false_runs_the_script_with_cascade_argv_zero(
    fcall_pipeline_spy,
):
    # Arrange - every aset_ttl call runs the cascade script; only the ARGV cascade flag differs.
    mock_pipe, mock_run_fcall = fcall_pipeline_spy
    mock_pipe.execute = AsyncMock(return_value=[[0, 0, 0]])
    root = CascadeChainRoot(head="CascadeChainNode:fake")

    with patch("rapyer.base._context_pipe") as mock_context_pipe:
        mock_context_pipe.get.return_value = None
        # Act
        result = await root.aset_ttl(TTL_SECONDS)

    # Assert
    mock_run_fcall.assert_called_once_with(
        mock_pipe,
        type(root).Meta.cascade_function_name,
        1,
        root.key,
        "CascadeChainRoot",
        SPECIAL_FIELD_KEY_PREFIX,
        TTL_SECONDS,
        0,
    )
    # A non-cascading call keeps the old None-return contract despite sharing the script.
    assert result is None


@pytest.mark.asyncio
async def test_aset_ttl_cascade_true_runs_the_script_with_cascade_argv_one(
    fcall_pipeline_spy,
):
    # Arrange
    mock_pipe, mock_run_fcall = fcall_pipeline_spy
    mock_pipe.execute = AsyncMock(return_value=[[0, 0, 0]])
    root = CascadeChainRoot(head="CascadeChainNode:fake")

    with patch("rapyer.base._context_pipe") as mock_context_pipe:
        mock_context_pipe.get.return_value = None
        # Act
        result = await root.aset_ttl(TTL_SECONDS, cascade=True)

    # Assert
    mock_run_fcall.assert_called_once_with(
        mock_pipe,
        type(root).Meta.cascade_function_name,
        1,
        root.key,
        "CascadeChainRoot",
        SPECIAL_FIELD_KEY_PREFIX,
        TTL_SECONDS,
        1,
    )
    assert result == CascadeResult(
        dangling_children=0, dangling_special=0, mismatched_class=0
    )


@pytest.mark.asyncio
async def test_aset_ttl_cascade_standalone_owns_execution_and_returns_cascade_result(
    fcall_pipeline_spy,
):
    # Arrange - standalone: enqueues run_sha, awaits pipe.execute() itself, decodes the result.
    mock_pipe, mock_run_fcall = fcall_pipeline_spy
    mock_pipe.execute = AsyncMock(return_value=[[1, 2, 0]])
    root = CascadeChainRoot(head="CascadeChainNode:fake")

    with patch("rapyer.base._context_pipe") as mock_context_pipe:
        mock_context_pipe.get.return_value = None
        # Act
        result = await root.aset_ttl(TTL_SECONDS, cascade=True)

    # Assert
    mock_run_fcall.assert_called_once_with(
        mock_pipe,
        type(root).Meta.cascade_function_name,
        1,
        root.key,
        "CascadeChainRoot",
        SPECIAL_FIELD_KEY_PREFIX,
        TTL_SECONDS,
        1,
    )
    mock_pipe.execute.assert_awaited_once()
    assert result == CascadeResult(
        dangling_children=1, dangling_special=2, mismatched_class=0
    )


@pytest.mark.asyncio
async def test_aset_ttl_cascade_standalone_awaits_pipe_execute_directly(
    fcall_pipeline_spy,
):
    # Arrange - the standalone branch awaits pipe.execute() bare and captures results[-1].
    # It does not yet self-heal a NOSCRIPT; tracked as a follow-up in NOSCRIPT-ISSUE.md.
    mock_pipe, _ = fcall_pipeline_spy
    mock_pipe.execute = AsyncMock(return_value=[[3, 4, 0]])
    root = CascadeChainRoot(head="CascadeChainNode:fake")

    with patch("rapyer.base._context_pipe") as mock_context_pipe:
        mock_context_pipe.get.return_value = None
        # Act
        result = await root.aset_ttl(TTL_SECONDS, cascade=True)

    # Assert
    mock_pipe.execute.assert_awaited_once()
    assert result == CascadeResult(
        dangling_children=3, dangling_special=4, mismatched_class=0
    )


@pytest.mark.asyncio
async def test_aset_ttl_cascade_inside_outer_pipeline_returns_none_without_executing(
    fcall_pipeline_spy,
):
    # Arrange - inside an outer pipeline: enqueues there, never executes, returns None.
    mock_pipe, mock_run_fcall = fcall_pipeline_spy
    mock_pipe.execute = AsyncMock()
    root = CascadeChainRoot(head="CascadeChainNode:fake")

    with patch("rapyer.base._context_pipe") as mock_context_pipe:
        mock_context_pipe.get.return_value = mock_pipe
        # Act
        result = await root.aset_ttl(TTL_SECONDS, cascade=True)

    # Assert
    mock_run_fcall.assert_called_once()
    mock_pipe.execute.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_aset_ttl_cascade_false_on_fk_edged_model_refreshes_only_root(
    setup_fake_redis_for_cascade_apply,
    fake_redis_client,
):
    # Arrange - end-to-end proof on real fakeredis that cascade=False follows no edge.
    child = await CascadeChainNode(name="child").asave()
    root = await CascadeChainRoot(head=child.key).asave()
    await fake_redis_client.persist(root.key)
    await fake_redis_client.persist(child.key)

    # Act
    result = await root.aset_ttl(TTL_SECONDS, cascade=False)

    # Assert
    assert result is None
    assert await fake_redis_client.ttl(root.key) > 0
    assert await fake_redis_client.ttl(child.key) in (-1, -2)
