from unittest.mock import AsyncMock, MagicMock

import pytest
from rapyer.errors import ScriptsNotInitializedError
from rapyer.scripts import (
    run_sha,
    handle_noscript_error,
    register_scripts,
    REMOVE_RANGE_SCRIPT_NAME,
    _REGISTERED_SCRIPT_SHAS,
)


@pytest.fixture
def clear_script_state():
    original_shas = _REGISTERED_SCRIPT_SHAS.copy()
    _REGISTERED_SCRIPT_SHAS.clear()
    yield
    _REGISTERED_SCRIPT_SHAS.clear()
    _REGISTERED_SCRIPT_SHAS.update(original_shas)


def test_run_sha_raises_scripts_not_initialized_error_when_scripts_not_loaded_error(
    clear_script_state,
):
    # Arrange
    pipeline = MagicMock()

    # Act & Assert
    with pytest.raises(ScriptsNotInitializedError) as exc_info:
        run_sha(pipeline, REMOVE_RANGE_SCRIPT_NAME, 1, "key", "$.path", 0, 5)

    assert "init_rapyer()" in str(exc_info.value)
    assert REMOVE_RANGE_SCRIPT_NAME in str(exc_info.value)


def test_run_sha_calls_evalsha_with_correct_args_sanity(clear_script_state):
    # Arrange
    pipeline = MagicMock()
    _REGISTERED_SCRIPT_SHAS[REMOVE_RANGE_SCRIPT_NAME] = "test_sha_123"

    # Act
    run_sha(pipeline, REMOVE_RANGE_SCRIPT_NAME, 1, "key", "$.path", 0, 5)

    # Assert
    pipeline.evalsha.assert_called_once_with("test_sha_123", 1, "key", "$.path", 0, 5)


@pytest.mark.asyncio
async def test_handle_noscript_error_reloads_scripts_sanity(clear_script_state):
    # Arrange
    mock_redis = AsyncMock()
    mock_redis.script_load = AsyncMock(return_value="new_sha_456")
    mock_config = MagicMock()
    mock_config.is_fake_redis = False

    # Act
    await handle_noscript_error(mock_redis, mock_config)

    # Assert
    mock_redis.script_load.assert_called()
    assert _REGISTERED_SCRIPT_SHAS.get(REMOVE_RANGE_SCRIPT_NAME) == "new_sha_456"


@pytest.mark.asyncio
async def test_handle_noscript_error_reloads_scripts_with_fakeredis(clear_script_state):
    # Arrange
    mock_redis = AsyncMock()
    mock_redis.script_load = AsyncMock(return_value="fakeredis_sha_789")
    mock_config = MagicMock()
    mock_config.is_fake_redis = True

    # Act
    await handle_noscript_error(mock_redis, mock_config)

    # Assert
    mock_redis.script_load.assert_called()
    assert _REGISTERED_SCRIPT_SHAS.get(REMOVE_RANGE_SCRIPT_NAME) == "fakeredis_sha_789"


@pytest.mark.asyncio
async def test_register_scripts_stores_shas_sanity(clear_script_state):
    # Arrange
    mock_redis = AsyncMock()
    mock_redis.script_load = AsyncMock(return_value="sha_789")

    # Act
    await register_scripts(mock_redis)

    # Assert
    assert _REGISTERED_SCRIPT_SHAS.get(REMOVE_RANGE_SCRIPT_NAME) == "sha_789"
