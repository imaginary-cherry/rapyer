from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio.client import Redis

from rapyer.config import RedisConfig
from rapyer.errors import MetaFrozenError
from rapyer.init import init_rapyer
from tests.models.simple_types import TaskModel, UserModelWithTTL


@pytest.fixture
def mock_redis_client():
    redis_mock = AsyncMock(spec=Redis)
    redis_mock.ft.return_value.dropindex = AsyncMock()
    redis_mock.ft.return_value.create_index = AsyncMock()
    redis_mock.script_load = AsyncMock(return_value="mock_sha")
    return redis_mock


@pytest.fixture
def cascade_models():
    yield [TaskModel, UserModelWithTTL]


def test_fresh_redis_config_ttl_assignment_never_raises_sanity():
    # Arrange
    # Act
    config = RedisConfig(ttl=30)

    # Assert
    assert config.ttl == 30


def test_frozen_redis_config_ttl_assignment_raises_and_leaves_ttl_unchanged_sanity():
    # Arrange
    config = RedisConfig(ttl=30)
    config._meta_locked = True

    # Act
    with pytest.raises(MetaFrozenError):
        config.ttl = 60

    # Assert
    assert config.ttl == 30


@pytest.mark.asyncio
async def test_two_sequential_init_rapyer_calls_with_different_ttls_both_succeed_sanity(
    mock_redis_client, cascade_models
):
    # Arrange
    # Scope to two edge-free fixtures so build_cascade_plan's
    # validate_cascade_ttl_targets is trivially satisfied, matching the
    # pattern in test_init_rapyer_cascade_ttl.py.
    with patch("rapyer.init.REDIS_MODELS", cascade_models):
        # Act
        await init_rapyer(mock_redis_client, ttl=30)
        await init_rapyer(mock_redis_client, ttl=60)

    # Assert
    for model in cascade_models:
        assert model.Meta.ttl == 60
