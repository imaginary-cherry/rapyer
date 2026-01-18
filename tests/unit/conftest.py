import pytest
import pytest_asyncio
from fakeredis import aioredis as fake_aioredis

from rapyer.scripts import register_scripts

pytest.register_assert_rewrite("tests.assertions")


@pytest_asyncio.fixture
async def fake_redis_client():
    client = fake_aioredis.FakeRedis(decode_responses=True)
    await register_scripts(client)
    yield client
    await client.aclose()
