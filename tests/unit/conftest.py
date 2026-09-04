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
    # Mark models fakeredis-backed so TTL refresh uses the EXPIRE fallback (no FCALL there).
    originals = {model: model.Meta.is_fake_redis for model in REDIS_MODELS}
    for model in REDIS_MODELS:
        model.Meta.is_fake_redis = True
    yield client
    for model, original in originals.items():
        model.Meta.is_fake_redis = original
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
