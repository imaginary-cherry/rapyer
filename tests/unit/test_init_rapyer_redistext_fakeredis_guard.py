from typing import ClassVar
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import Field
from redis.asyncio.client import Redis

from rapyer.base import AtomicRedisModel, RedisConfig
from rapyer.errors import RedisTextRealRedisRequiredError
from rapyer.init import init_rapyer
from rapyer.types.redis_set import RedisSet
from rapyer.types.text import RedisText


class DirectRedisTextModel(AtomicRedisModel):
    body: RedisText = ""

    Meta: ClassVar[RedisConfig] = RedisConfig()


class NoRedisTextModel(AtomicRedisModel):
    name: str = ""
    count: int = 0

    Meta: ClassVar[RedisConfig] = RedisConfig()


class RedisSetOnlyModel(AtomicRedisModel):
    tags: RedisSet[str] = Field(default_factory=RedisSet[str])

    Meta: ClassVar[RedisConfig] = RedisConfig()


class InnerRedisTextModel(AtomicRedisModel):
    body: RedisText = ""

    Meta: ClassVar[RedisConfig] = RedisConfig()


class OuterNestedRedisTextModel(AtomicRedisModel):
    inner: InnerRedisTextModel = Field(default_factory=InnerRedisTextModel)

    Meta: ClassVar[RedisConfig] = RedisConfig()


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
async def test_direct_redistext_field_raises_when_fakeredis_detected(
    monkeypatch, mock_redis_client
):
    monkeypatch.setattr("rapyer.init.is_fakeredis", lambda client: True)
    with patch("rapyer.init.REDIS_MODELS", [DirectRedisTextModel]):
        with pytest.raises(RedisTextRealRedisRequiredError) as exc_info:
            await init_rapyer(mock_redis_client)

    assert exc_info.value.model_name == "DirectRedisTextModel"


@pytest.mark.asyncio
async def test_no_redistext_field_does_not_raise_when_fakeredis_detected(
    monkeypatch, mock_redis_client
):
    monkeypatch.setattr("rapyer.init.is_fakeredis", lambda client: True)
    with patch("rapyer.init.REDIS_MODELS", [NoRedisTextModel]):
        await init_rapyer(mock_redis_client)


@pytest.mark.asyncio
async def test_redis_set_only_model_does_not_raise_when_fakeredis_detected(
    monkeypatch, mock_redis_client
):
    monkeypatch.setattr("rapyer.init.is_fakeredis", lambda client: True)
    with patch("rapyer.init.REDIS_MODELS", [RedisSetOnlyModel]):
        await init_rapyer(mock_redis_client)


@pytest.mark.asyncio
async def test_nested_redistext_field_raises_when_fakeredis_detected(
    monkeypatch, mock_redis_client
):
    monkeypatch.setattr("rapyer.init.is_fakeredis", lambda client: True)
    with patch("rapyer.init.REDIS_MODELS", [OuterNestedRedisTextModel]):
        with pytest.raises(RedisTextRealRedisRequiredError) as exc_info:
            await init_rapyer(mock_redis_client)

    assert exc_info.value.model_name == "OuterNestedRedisTextModel"


@pytest.mark.asyncio
async def test_direct_redistext_field_does_not_raise_with_real_client(
    mock_redis_client,
):
    with patch("rapyer.init.REDIS_MODELS", [DirectRedisTextModel]):
        await init_rapyer(mock_redis_client)


@pytest.mark.asyncio
async def test_nested_redistext_field_does_not_raise_with_real_client(
    mock_redis_client,
):
    with patch("rapyer.init.REDIS_MODELS", [OuterNestedRedisTextModel]):
        await init_rapyer(mock_redis_client)
