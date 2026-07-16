from unittest.mock import AsyncMock, patch

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
    redis_mock.function_load = AsyncMock(return_value="mock_lib")
    redis_mock.set = AsyncMock()
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
    # Scope the blanket-enable to just the two fixtures under test — both
    # have zero relational/FK fields of their own, so patching REDIS_MODELS
    # down to this pair keeps the cascade graph edge-free and
    # validate_cascade_ttl_targets trivially passes, instead of newly
    # requiring Meta.ttl on every unrelated FK-target class in the whole
    # global registry (FkAuthor, FkTree, ...).
    with patch("rapyer.init.REDIS_MODELS", cascade_models):
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
