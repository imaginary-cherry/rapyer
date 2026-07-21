from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio.client import Redis

from rapyer.base import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.init import init_rapyer


class _FakeEmbeddingAdapter:
    """Minimal EmbeddingAdapter double - structurally matches the Protocol."""

    @property
    def dims(self):
        return 3

    async def aembed(self, content):
        return [0.1, 0.2, 0.3]

    async def aembed_many(self, contents):
        return [[0.1, 0.2, 0.3] for _ in contents]


class NoPresetVectorizerModel(AtomicRedisModel):
    name: str = ""


class PresetVectorizerModel(AtomicRedisModel):
    name: str = ""

    Meta = RedisConfig(vectorizer=_FakeEmbeddingAdapter())


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
def vectorizer_models():
    yield [NoPresetVectorizerModel, PresetVectorizerModel]


@pytest.mark.asyncio
async def test_init_rapyer_with_vectorizer_sets_exact_instance_on_non_preset_models_sanity(
    mock_redis_client, vectorizer_models
):
    # Arrange
    custom_adapter = _FakeEmbeddingAdapter()

    # Act
    with patch("rapyer.init.REDIS_MODELS", vectorizer_models):
        await init_rapyer(mock_redis_client, vectorizer=custom_adapter)

    # Assert
    assert NoPresetVectorizerModel.Meta.vectorizer is custom_adapter


@pytest.mark.asyncio
async def test_init_rapyer_without_vectorizer_arg_uses_packaged_default_sanity(
    mock_redis_client, vectorizer_models
):
    # Act
    with patch("rapyer.init.REDIS_MODELS", vectorizer_models):
        await init_rapyer(mock_redis_client)

    # Assert
    assert NoPresetVectorizerModel.Meta.vectorizer is not None


@pytest.mark.asyncio
async def test_init_rapyer_preset_vectorizer_survives_global_param_sanity(
    mock_redis_client, vectorizer_models
):
    # Arrange
    preset_adapter = PresetVectorizerModel.Meta.vectorizer
    other_adapter = _FakeEmbeddingAdapter()

    # Act
    with patch("rapyer.init.REDIS_MODELS", vectorizer_models):
        await init_rapyer(mock_redis_client, vectorizer=other_adapter)

    # Assert
    assert PresetVectorizerModel.Meta.vectorizer is preset_adapter


@pytest.mark.asyncio
async def test_init_rapyer_reinit_updates_non_preset_model_without_flagging_preset_sanity(
    mock_redis_client, vectorizer_models
):
    # Arrange
    first_adapter = _FakeEmbeddingAdapter()
    second_adapter = _FakeEmbeddingAdapter()

    # Act
    with patch("rapyer.init.REDIS_MODELS", vectorizer_models):
        await init_rapyer(mock_redis_client, vectorizer=first_adapter)
        first_result = NoPresetVectorizerModel.Meta.vectorizer
        first_preset_flag = NoPresetVectorizerModel.Meta._vectorizer_preset
        await init_rapyer(mock_redis_client, vectorizer=second_adapter)

    # Assert
    assert first_result is first_adapter
    assert first_preset_flag is False
    assert NoPresetVectorizerModel.Meta.vectorizer is second_adapter
    assert NoPresetVectorizerModel.Meta._vectorizer_preset is False
