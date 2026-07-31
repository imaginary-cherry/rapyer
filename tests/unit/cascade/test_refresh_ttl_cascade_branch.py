import pytest

from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import CascadeAuthor, CascadeChainRoot


@pytest.mark.asyncio
async def test_refresh_ttl_cascade_enabled_model_calls_run_sha_not_expire(
    fcall_pipeline_spy,
):
    # Arrange
    mock_pipe, mock_run_fcall = fcall_pipeline_spy
    root = CascadeChainRoot(head="CascadeChainNode:fake")

    # Act
    await root.refresh_ttl(can_use_pipeline=True)

    # Assert
    mock_run_fcall.assert_called_once_with(
        mock_pipe,
        type(root).Meta.cascade_function_name,
        1,
        root.key,
        "CascadeChainRoot",
        SPECIAL_FIELD_KEY_PREFIX,
        root.Meta.ttl,
        1,
    )
    mock_pipe.expire.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_ttl_non_cascade_model_uses_plain_expire_not_the_script(
    fcall_pipeline_spy,
):
    # Arrange
    mock_pipe, mock_run_fcall = fcall_pipeline_spy
    author = CascadeAuthor()

    # Act
    await author.refresh_ttl(can_use_pipeline=True)

    # Assert
    mock_run_fcall.assert_not_called()
    mock_pipe.expire.assert_called_once_with(author.key, author.Meta.ttl)
