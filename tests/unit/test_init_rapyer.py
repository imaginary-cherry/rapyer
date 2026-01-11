from unittest.mock import Mock, patch, AsyncMock

import pytest
from rapyer.init import init_rapyer, teardown_rapyer
from redis import ResponseError
from redis.asyncio.client import Redis
from tests.models.collection_types import IntListModel, ProductListModel, StrListModel
from tests.models.index_types import IndexTestModel
from tests.models.simple_types import (
    NoneTestModel,
    TaskModel,
    UserModelWithoutTTL,
    UserModelWithTTL,
)


@pytest.fixture
def mock_redis_client():
    redis_mock = AsyncMock(spec=Redis)
    redis_mock.ft.return_value.dropindex = AsyncMock()
    redis_mock.ft.return_value.create_index = AsyncMock()
    return redis_mock


@pytest.fixture
def redis_models():
    yield [
        ProductListModel,
        IntListModel,
        StrListModel,
        UserModelWithTTL,
        UserModelWithoutTTL,
        TaskModel,
        NoneTestModel,
    ]


@pytest.mark.asyncio
async def test_init_rapyer_with_redis_client_sanity(mock_redis_client, redis_models):
    # Arrange
    NoneTestModel.Meta.ttl = 30

    # Act
    await init_rapyer(mock_redis_client)

    # Assert
    for model in redis_models:
        assert model.Meta.redis is mock_redis_client
    assert NoneTestModel.Meta.ttl == 30


@patch("rapyer.init.redis_async.from_url")
@pytest.mark.asyncio
async def test_init_rapyer_with_string_connection_sanity(
    mock_from_url, redis_models, mock_redis_client
):
    # Arrange
    connection_string = "redis://localhost:6379"
    mock_from_url.return_value = mock_redis_client

    # Act
    await init_rapyer(connection_string)

    # Assert
    mock_from_url.assert_called_once_with(
        connection_string, decode_responses=True, max_connections=20
    )
    for model in redis_models:
        assert model.Meta.redis is mock_redis_client


@pytest.mark.asyncio
async def test_init_rapyer_with_ttl_sanity(mock_redis_client, redis_models):
    # Arrange
    ttl_value = 120

    # Act
    await init_rapyer(mock_redis_client, ttl=ttl_value)

    # Assert
    for model in redis_models:
        assert model.Meta.redis is mock_redis_client
        assert model.Meta.ttl == ttl_value


@pytest.mark.asyncio
async def test_init_rapyer_with_existing_redis_client_no_override_sanity(redis_models):
    # Arrange
    existing_redis_client = Mock(spec=Redis)
    TaskModel.Meta.redis = existing_redis_client

    # Act
    await init_rapyer(ttl=300)

    # Assert
    assert TaskModel.Meta.redis is existing_redis_client
    assert TaskModel.Meta.ttl == 300


@pytest.mark.asyncio
async def test_init_rapyer_override_existing_redis_and_ttl_sanity(
    mock_redis_client, redis_models
):
    # Arrange
    old_redis_client = Mock(spec=Redis)
    old_ttl = 60
    new_ttl = 240

    UserModelWithTTL.Meta.redis = old_redis_client
    UserModelWithTTL.Meta.ttl = old_ttl
    TaskModel.Meta.redis = old_redis_client
    TaskModel.Meta.ttl = old_ttl

    # Act
    await init_rapyer(mock_redis_client, ttl=new_ttl)

    # Assert
    assert UserModelWithTTL.Meta.redis is mock_redis_client
    assert UserModelWithTTL.Meta.ttl == new_ttl
    assert TaskModel.Meta.redis is mock_redis_client
    assert TaskModel.Meta.ttl == new_ttl


@pytest.mark.asyncio
async def test_teardown_rapyer_calls_aclose_once_per_unique_client_sanity():
    # Arrange
    mock_redis = AsyncMock(spec=Redis)
    UserModelWithTTL.Meta.redis = mock_redis
    TaskModel.Meta.redis = mock_redis

    # Act
    await teardown_rapyer()

    # Assert
    mock_redis.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_init_rapyer_raises_response_error_when_acreate_index_fails_with_override_error():
    # Arrange
    mock_redis = AsyncMock(spec=Redis)
    mock_redis.ft.return_value.dropindex = AsyncMock()

    with patch.object(
        IndexTestModel,
        "acreate_index",
        AsyncMock(side_effect=ResponseError("Index error")),
    ):
        # Act & Assert
        with pytest.raises(ResponseError):
            await init_rapyer(mock_redis, override_old_idx=True)
