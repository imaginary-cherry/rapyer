import logging
from unittest.mock import Mock, patch, AsyncMock

import pytest
from rapyer.init import init_rapyer, teardown_rapyer
from rapyer.scripts import SCRIPTS
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
from tests.models.unknown_types import (
    ModelWithPreferJsonDumpConfig,
    ModelWithStrEnumDefault,
)


@pytest.fixture
def mock_redis_client():
    redis_mock = AsyncMock(spec=Redis)
    redis_mock.ft.return_value.dropindex = AsyncMock()
    redis_mock.ft.return_value.create_index = AsyncMock()
    redis_mock.script_load = AsyncMock(return_value="mock_sha")
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
    mock_redis.script_load = AsyncMock(return_value="mock_sha")

    with patch.object(
        IndexTestModel,
        "acreate_index",
        AsyncMock(side_effect=ResponseError("Index error")),
    ):
        # Act & Assert
        with pytest.raises(ResponseError):
            await init_rapyer(mock_redis, override_old_idx=True)


@pytest.mark.asyncio
async def test_init_rapyer_with_prefer_normal_json_dump_overrides_all_models_sanity():
    # Arrange
    original_preconfigured = ModelWithPreferJsonDumpConfig.Meta.prefer_normal_json_dump
    original_default = ModelWithStrEnumDefault.Meta.prefer_normal_json_dump

    # Act
    await init_rapyer(prefer_normal_json_dump=False)

    # Assert
    assert ModelWithPreferJsonDumpConfig.Meta.prefer_normal_json_dump is False
    assert ModelWithStrEnumDefault.Meta.prefer_normal_json_dump is False
    ModelWithPreferJsonDumpConfig.Meta.prefer_normal_json_dump = original_preconfigured
    ModelWithStrEnumDefault.Meta.prefer_normal_json_dump = original_default


@pytest.mark.asyncio
async def test_init_rapyer_without_prefer_normal_json_dump_keeps_preconfigured_values_sanity():
    # Arrange
    original_preconfigured = ModelWithPreferJsonDumpConfig.Meta.prefer_normal_json_dump
    original_default = ModelWithStrEnumDefault.Meta.prefer_normal_json_dump
    ModelWithPreferJsonDumpConfig.Meta.prefer_normal_json_dump = True
    ModelWithStrEnumDefault.Meta.prefer_normal_json_dump = False

    # Act
    await init_rapyer()

    # Assert
    assert ModelWithPreferJsonDumpConfig.Meta.prefer_normal_json_dump is True
    assert ModelWithStrEnumDefault.Meta.prefer_normal_json_dump is False
    ModelWithPreferJsonDumpConfig.Meta.prefer_normal_json_dump = original_preconfigured
    ModelWithStrEnumDefault.Meta.prefer_normal_json_dump = original_default


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["script_name", "script_text"],
    [[name, text] for name, text in SCRIPTS.items()],
)
async def test_init_rapyer_loads_all_scripts_sanity(
    mock_redis_client, script_name, script_text
):
    # Arrange & Act
    await init_rapyer(mock_redis_client)

    # Assert
    mock_redis_client.script_load.assert_any_call(script_text)


@pytest.mark.asyncio
async def test_init_rapyer_with_logger_configures_rapyer_logger_sanity():
    # Arrange
    custom_logger = logging.getLogger("custom_test_logger")
    custom_logger.setLevel(logging.DEBUG)
    custom_handler = logging.StreamHandler()
    custom_logger.handlers.clear()
    custom_logger.addHandler(custom_handler)

    # Act
    await init_rapyer(logger=custom_logger)

    # Assert
    rapyer_logger = logging.getLogger("rapyer")
    assert rapyer_logger.level == logging.DEBUG
    assert custom_handler in rapyer_logger.handlers


@pytest.mark.asyncio
async def test_init_rapyer_without_logger_does_not_modify_rapyer_logger_sanity():
    # Arrange
    rapyer_logger = logging.getLogger("rapyer")
    original_level = rapyer_logger.level
    original_handlers = rapyer_logger.handlers.copy()

    # Act
    await init_rapyer()

    # Assert
    assert rapyer_logger.level == original_level
    assert rapyer_logger.handlers == original_handlers
