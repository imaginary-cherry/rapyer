from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest

from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import CascadeAuthor, CascadeChainRoot


@pytest.mark.asyncio
async def test_refresh_ttl_cascade_enabled_model_calls_run_sha_not_expire():
    # Arrange
    root = CascadeChainRoot(head="CascadeChainNode:fake")
    mock_pipe = MagicMock()

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta):
        yield mock_pipe

    with (
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_fcall") as mock_run_fcall,
    ):
        # Act
        await root.refresh_ttl(can_use_pipeline=True)

    # Assert
    mock_run_fcall.assert_called_once_with(
        mock_pipe,
        1,
        root.key,
        "CascadeChainRoot",
        SPECIAL_FIELD_KEY_PREFIX,
        root.Meta.ttl,
        1,
    )
    mock_pipe.expire.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_ttl_non_cascade_model_also_calls_run_sha():
    # Arrange
    # refresh_ttl always routes through the cascade script; a model with no
    # outgoing edges just re-arms its own keys via the script, never expire.
    author = CascadeAuthor()
    mock_pipe = MagicMock()

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta):
        yield mock_pipe

    with (
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_fcall") as mock_run_fcall,
    ):
        # Act
        await author.refresh_ttl(can_use_pipeline=True)

    # Assert
    mock_run_fcall.assert_called_once_with(
        mock_pipe,
        1,
        author.key,
        "CascadeAuthor",
        SPECIAL_FIELD_KEY_PREFIX,
        author.Meta.ttl,
        1,
    )
    mock_pipe.expire.assert_not_called()
