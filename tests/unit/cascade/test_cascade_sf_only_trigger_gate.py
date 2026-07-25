from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest

from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import (
    CascadePQRefParent,
    CascadeSetRefOptOut,
    CascadeSetRefParent,
)


@pytest.mark.asyncio
async def test_set_ref_parent_refresh_ttl_calls_run_fcall_not_expire():
    # Arrange: SF-only parent, sole cascade edge is its per-field-enabled `refs` set.
    parent = CascadeSetRefParent()
    mock_pipe = MagicMock()

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta):
        yield mock_pipe

    with (
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_fcall") as mock_run_fcall,
    ):
        # Act
        await parent.refresh_ttl(can_use_pipeline=True)

    # Assert
    mock_run_fcall.assert_called_once_with(
        mock_pipe,
        type(parent).Meta.cascade_function_name,
        1,
        parent.key,
        "CascadeSetRefParent",
        SPECIAL_FIELD_KEY_PREFIX,
        parent.Meta.ttl,
        1,
    )
    mock_pipe.expire.assert_not_called()


@pytest.mark.asyncio
async def test_pq_ref_parent_refresh_ttl_calls_run_fcall_not_expire():
    # Arrange: same shape, RedisPriorityQueue instead of RedisSet.
    parent = CascadePQRefParent()
    mock_pipe = MagicMock()

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta):
        yield mock_pipe

    with (
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_fcall") as mock_run_fcall,
    ):
        # Act
        await parent.refresh_ttl(can_use_pipeline=True)

    # Assert
    mock_run_fcall.assert_called_once_with(
        mock_pipe,
        type(parent).Meta.cascade_function_name,
        1,
        parent.key,
        "CascadePQRefParent",
        SPECIAL_FIELD_KEY_PREFIX,
        parent.Meta.ttl,
        1,
    )
    mock_pipe.expire.assert_not_called()


@pytest.mark.asyncio
async def test_set_ref_opt_out_refresh_ttl_still_uses_plain_expire():
    # Arrange: sole SF field opts OUT via a per-field CascadeTTL(enabled=False).
    parent = CascadeSetRefOptOut()
    mock_pipe = MagicMock()

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta):
        yield mock_pipe

    with (
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_fcall") as mock_run_fcall,
    ):
        # Act
        await parent.refresh_ttl(can_use_pipeline=True)

    # Assert (all_keys includes the opted-out `refs` SF key, not just the main key)
    mock_run_fcall.assert_not_called()
    expected_calls = [((key, parent.Meta.ttl),) for key in parent.all_keys]
    actual_calls = [call.args for call in mock_pipe.expire.call_args_list]
    assert actual_calls == [args for (args,) in expected_calls]
