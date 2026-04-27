import pytest
import pytest_asyncio
from fakeredis import aioredis as fake_aioredis

from rapyer.base import REDIS_MODELS
from rapyer.scripts import register_scripts

pytest.register_assert_rewrite("tests.assertions")


@pytest_asyncio.fixture
async def fake_redis_client():
    client = fake_aioredis.FakeRedis(decode_responses=True)
    await register_scripts(client, is_fakeredis=True)
    yield client
    await client.aclose()


@pytest.fixture
def restore_redis_models():
    original = REDIS_MODELS.copy()
    yield
    REDIS_MODELS.clear()
    REDIS_MODELS.extend(original)


@pytest.fixture
def clean_redis_models(restore_redis_models):
    REDIS_MODELS.clear()
