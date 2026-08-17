import pytest

from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import (
    CascadePQRefParent,
    CascadeSetRefOptOut,
    CascadeSetRefParent,
)


@pytest.mark.asyncio
async def test_set_ref_parent_refresh_ttl_calls_run_fcall_not_expire(
    fcall_pipeline_spy,
):
    # Arrange: SF-only parent, sole cascade edge is its per-field-enabled `refs` set.
    mock_pipe, mock_run_fcall = fcall_pipeline_spy
    parent = CascadeSetRefParent()

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
async def test_pq_ref_parent_refresh_ttl_calls_run_fcall_not_expire(
    fcall_pipeline_spy,
):
    # Arrange: same shape, RedisPriorityQueue instead of RedisSet.
    mock_pipe, mock_run_fcall = fcall_pipeline_spy
    parent = CascadePQRefParent()

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
async def test_set_ref_opt_out_refresh_ttl_gates_like_a_normal_opt_out_fk(
    fcall_pipeline_spy,
):
    """A cascade-opt-out SF field gates like any opt-out FK: _needs_cascade_script is
    True, so refresh_ttl takes the FCALL path. The plan carries no enabled edge, so the
    FCALL refreshes only the parent's own keys and follows no reference (no child)."""
    mock_pipe, mock_run_fcall = fcall_pipeline_spy
    parent = CascadeSetRefOptOut()

    # Act
    await parent.refresh_ttl(can_use_pipeline=True)

    # Assert
    mock_run_fcall.assert_called_once_with(
        mock_pipe,
        type(parent).Meta.cascade_function_name,
        1,
        parent.key,
        "CascadeSetRefOptOut",
        SPECIAL_FIELD_KEY_PREFIX,
        parent.Meta.ttl,
        1,
    )
    mock_pipe.expire.assert_not_called()
