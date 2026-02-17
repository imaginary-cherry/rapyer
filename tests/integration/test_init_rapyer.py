import pytest
import rapyer
import redis
from rapyer.base import REDIS_MODELS


@pytest.mark.asyncio
async def test_init_rapyer_with_url__redis_is_available():
    # Arrange
    redis_url = "redis://localhost:6370"

    # Act
    await rapyer.init_rapyer(redis_url)

    for model in REDIS_MODELS:
        await model.Meta.redis.ping()
        assert model.Meta.redis.connection_pool.connection_kwargs["decode_responses"]


@pytest.mark.asyncio
async def test_init_rapyer_with_client__redis_is_available():
    # Arrange
    created_client = redis.asyncio.from_url(
        "redis://localhost:6370/0", decode_responses=True
    )

    # Act
    await rapyer.init_rapyer(created_client)

    for model in REDIS_MODELS:
        await model.Meta.redis.ping()
