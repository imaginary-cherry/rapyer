from typing import Annotated, ClassVar
from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio.client import Redis

from rapyer.base import AtomicRedisModel, RedisConfig
from rapyer.errors import VectorDimMismatchError
from rapyer.fields.vector import Vector
from rapyer.init import init_rapyer
from rapyer.types.text import RedisText


class _FakeEmbeddingAdapter:
    """Minimal EmbeddingAdapter double - structurally matches the Protocol."""

    @property
    def dims(self):
        return 3

    async def aembed(self, content):
        return [0.1, 0.2, 0.3]

    async def aembed_many(self, contents):
        return [[0.1, 0.2, 0.3] for _ in contents]


class MatchingDimModel(AtomicRedisModel):
    body: Annotated[RedisText, Vector(dim=3)] = ""

    Meta: ClassVar[RedisConfig] = RedisConfig()


class MismatchedDimModel(AtomicRedisModel):
    body: Annotated[RedisText, Vector(dim=768)] = ""

    Meta: ClassVar[RedisConfig] = RedisConfig()


class BareTextNoVectorModel(AtomicRedisModel):
    body: RedisText = ""

    Meta: ClassVar[RedisConfig] = RedisConfig()


class PresetVectorizerMatchingDimModel(AtomicRedisModel):
    body: Annotated[RedisText, Vector(dim=3)] = ""

    Meta: ClassVar[RedisConfig] = RedisConfig(vectorizer=_FakeEmbeddingAdapter())


@pytest.fixture
def mock_redis_client():
    redis_mock = AsyncMock(spec=Redis)
    redis_mock.ft.return_value.dropindex = AsyncMock()
    redis_mock.ft.return_value.create_index = AsyncMock()
    redis_mock.script_load = AsyncMock(return_value="mock_sha")
    redis_mock.function_load = AsyncMock(return_value="mock_lib")
    redis_mock.set = AsyncMock()
    return redis_mock


@pytest.mark.asyncio
async def test_matching_dim_passes_init_rapyer(mock_redis_client):
    with patch("rapyer.init.REDIS_MODELS", [MatchingDimModel]):
        await init_rapyer(mock_redis_client, vectorizer=_FakeEmbeddingAdapter())


@pytest.mark.asyncio
async def test_mismatched_dim_raises_vector_dim_mismatch_error(mock_redis_client):
    with patch("rapyer.init.REDIS_MODELS", [MismatchedDimModel]):
        with pytest.raises(VectorDimMismatchError) as exc_info:
            await init_rapyer(mock_redis_client, vectorizer=_FakeEmbeddingAdapter())

    assert exc_info.value.field_name == "body"
    assert exc_info.value.declared_dim == 768
    assert exc_info.value.actual_dim == 3


@pytest.mark.asyncio
async def test_bare_redistext_field_skips_dim_validation(mock_redis_client):
    with patch("rapyer.init.REDIS_MODELS", [BareTextNoVectorModel]):
        await init_rapyer(mock_redis_client, vectorizer=_FakeEmbeddingAdapter())


@pytest.mark.asyncio
async def test_matching_dim_with_preset_vectorizer_passes(mock_redis_client):
    with patch("rapyer.init.REDIS_MODELS", [PresetVectorizerMatchingDimModel]):
        await init_rapyer(mock_redis_client)


@pytest.mark.asyncio
async def test_meta_locked_restored_after_dim_mismatch_error(mock_redis_client):
    with patch("rapyer.init.REDIS_MODELS", [MismatchedDimModel]):
        with pytest.raises(VectorDimMismatchError):
            await init_rapyer(mock_redis_client, vectorizer=_FakeEmbeddingAdapter())

    assert MismatchedDimModel.Meta._meta_locked is True
