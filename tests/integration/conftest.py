import os
from dataclasses import dataclass
from typing import Generic, TypeVar
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

import rapyer
from rapyer.base import REDIS_MODELS
from rapyer.cascade.planner import (
    build_cascade_plan,
    cascade_plan_json,
)
from rapyer.result import resolve_forward_refs
from rapyer.scripts import register_cascade_function, register_scripts
from rapyer.types.relational import resolve_relational_targets
from tests.models.registry import TESTED_REDIS_MODELS
from tests.models.simple_types import TTLRefreshDisabledModel, TTLRefreshTestModel

REDUCED_TTL_SECONDS = 10

T = TypeVar("T")


@dataclass
class SavedModelWithReducedTTL(Generic[T]):
    model: T
    initial_ttl: int


@pytest_asyncio.fixture
async def redis_client():
    meta_redis = rapyer.AtomicRedisModel.Meta.redis
    db_num = os.getenv("REDIS_DB", "0")
    redis = meta_redis.from_url(
        f"redis://localhost:6370/{db_num}", decode_responses=True
    )
    await redis.flushdb()
    yield redis
    await redis.flushdb()


@pytest_asyncio.fixture
async def requires_redis_functions(redis_client):
    info = await redis_client.info("server")
    major = int(str(info.get("redis_version", "0")).split(".")[0])
    if major < 7:
        pytest.skip("TTL cascade requires Redis 7+ (Redis Functions)")


@pytest_asyncio.fixture(autouse=True)
async def real_redis_client(redis_client):
    resolve_forward_refs()
    resolve_relational_targets(REDIS_MODELS)

    # Configure Redis client for all models
    for model in TESTED_REDIS_MODELS:
        model.Meta.redis = redis_client

    # Register Lua scripts
    await register_scripts(redis_client)

    # Emulate init_rapyer: load the cascade Redis Function for refresh_ttl's FCALL path.
    await register_cascade_function(
        redis_client, cascade_plan_json(build_cascade_plan(REDIS_MODELS))
    )

    yield redis_client

    await redis_client.aclose()


@pytest_asyncio.fixture
async def saved_model_with_reduced_ttl(real_redis_client):
    model = TTLRefreshTestModel(
        name="ttl_test",
        age=25,
        score=10.5,
        tags=["tag1", "tag2"],
        settings={"key1": "value1", "key2": "value2"},
    )
    await model.asave()
    await real_redis_client.expire(model.key, REDUCED_TTL_SECONDS)
    initial_ttl = await real_redis_client.ttl(model.key)

    yield SavedModelWithReducedTTL(model=model, initial_ttl=initial_ttl)

    await model.adelete()


@pytest_asyncio.fixture
async def flush_scripts(real_redis_client):
    await real_redis_client.execute_command("SCRIPT", "FLUSH")
    yield


@pytest.fixture
def disable_noscript_recovery():
    with patch("rapyer.scripts.registry.handle_noscript_error", new_callable=AsyncMock):
        yield


@pytest_asyncio.fixture
async def saved_no_refresh_model_with_reduced_ttl(real_redis_client):
    model = TTLRefreshDisabledModel(
        name="ttl_no_refresh_test",
        age=25,
        score=10.5,
        tags=["tag1", "tag2"],
        settings={"key1": "value1", "key2": "value2"},
    )
    await model.asave()
    await real_redis_client.expire(model.key, REDUCED_TTL_SECONDS)
    initial_ttl = await real_redis_client.ttl(model.key)

    yield SavedModelWithReducedTTL(model=model, initial_ttl=initial_ttl)

    await model.adelete()
