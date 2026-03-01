import asyncio
import os

import pytest

import rapyer
from rapyer.init import init_rapyer, teardown_rapyer


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def redis_client(event_loop):
    meta_redis = rapyer.AtomicRedisModel.Meta.redis
    db_num = os.getenv("REDIS_DB", "0")
    redis = meta_redis.from_url(
        f"redis://localhost:6370/{db_num}", decode_responses=True
    )
    event_loop.run_until_complete(redis.flushdb())
    yield redis
    event_loop.run_until_complete(redis.flushdb())


@pytest.fixture(autouse=True)
def real_redis_client(redis_client, event_loop):
    event_loop.run_until_complete(init_rapyer(redis=redis_client))

    yield redis_client

    event_loop.run_until_complete(teardown_rapyer())
