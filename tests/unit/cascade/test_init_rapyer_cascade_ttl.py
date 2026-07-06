from unittest.mock import AsyncMock

import pytest
from redis.asyncio.client import Redis

from rapyer.cascade import CascadeTTL
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


@pytest.mark.asyncio
async def test_init_rapyer_with_cascade_ttl_sets_exact_instance_on_every_model_sanity(
    mock_redis_client, cascade_models
):
    # Arrange
    cascade_ttl = CascadeTTL()

    # Act
    await init_rapyer(mock_redis_client, cascade_ttl=cascade_ttl)

    # Assert
    for model in cascade_models:
        assert model.Meta.cascade_ttl == cascade_ttl


@pytest.mark.asyncio
async def test_init_rapyer_without_cascade_ttl_resets_prior_value_to_none_sanity(
    mock_redis_client, cascade_models
):
    # Arrange
    UserModelWithTTL.Meta.cascade_ttl = CascadeTTL(depth=5)

    # Act
    await init_rapyer(mock_redis_client)

    # Assert
    assert UserModelWithTTL.Meta.cascade_ttl is None
