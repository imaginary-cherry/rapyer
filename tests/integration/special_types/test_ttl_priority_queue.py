import pytest
import pytest_asyncio

from rapyer.base import AtomicRedisModel
from rapyer.types.priority_queue import PriorityQueueItem, RedisPriorityQueue
from tests.conftest import (
    special_field_test_for,
    special_field_ttl_test_for,
)
from tests.integration.conftest import REDUCED_TTL_SECONDS, SavedModelWithReducedTTL
from tests.models.simple_types import TTL_TEST_SECONDS
from tests.models.special_types import (
    PriorityQueueModel,
    PriorityQueueModelBase,
)


async def create_pq_model(real_redis_client, model: PriorityQueueModelBase):
    await model.asave()
    await model.tasks.apush("high", 1.0)
    await model.tasks.apush("medium", 2.0)
    await model.tasks.apush("low", 3.0)

    await real_redis_client.expire(model.key, REDUCED_TTL_SECONDS)
    await real_redis_client.expire(model.tasks.special_key, REDUCED_TTL_SECONDS)
    initial_ttl = await real_redis_client.ttl(model.tasks.special_key)

    yield SavedModelWithReducedTTL(model=model, initial_ttl=initial_ttl)

    await model.adelete()


@pytest_asyncio.fixture
async def saved_pq_ttl_model_with_reduced_ttl(real_redis_client):
    model = PriorityQueueModel(name="pq_ttl_test")
    async for result in create_pq_model(real_redis_client, model):
        yield result


async def assert_ttl_refreshed(real_redis_client, initial_ttl, *keys):
    for key in keys:
        ttl = await real_redis_client.ttl(key)
        assert ttl > initial_ttl
        assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS


async def assert_ttl_not_refreshed(real_redis_client, initial_ttl, *keys):
    for key in keys:
        ttl = await real_redis_client.ttl(key)
        assert ttl <= initial_ttl
        assert 0 < ttl <= REDUCED_TTL_SECONDS



# --- Base model action PQ key TTL tests ---


@special_field_ttl_test_for(AtomicRedisModel.aload, RedisPriorityQueue)
@pytest.mark.asyncio
async def test_ttl_refresh_pq_key_on_aload(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    await model.aload()

    # Assert
    await assert_ttl_refreshed(
        real_redis_client, initial_ttl, model.tasks.special_key, model.key
    )


@special_field_ttl_test_for(AtomicRedisModel.aget, RedisPriorityQueue)
@pytest.mark.asyncio
async def test_ttl_refresh_pq_key_on_aget(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    await PriorityQueueModel.aget(model.key)

    # Assert
    await assert_ttl_refreshed(
        real_redis_client, initial_ttl, model.tasks.special_key, model.key
    )


@special_field_ttl_test_for(AtomicRedisModel.afind, RedisPriorityQueue)
@pytest.mark.asyncio
async def test_ttl_refresh_pq_key_on_afind(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    await PriorityQueueModel.afind()

    # Assert
    await assert_ttl_refreshed(
        real_redis_client, initial_ttl, model.tasks.special_key, model.key
    )


@special_field_ttl_test_for(AtomicRedisModel.afind_one, RedisPriorityQueue)
@pytest.mark.asyncio
async def test_ttl_refresh_pq_key_on_afind_one(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    await PriorityQueueModel.afind_one(model.key)

    # Assert
    await assert_ttl_refreshed(
        real_redis_client, initial_ttl, model.tasks.special_key, model.key
    )


@special_field_test_for(AtomicRedisModel.refresh_ttl_if_needed, RedisPriorityQueue)
@pytest.mark.asyncio
async def test_refresh_ttl_if_needed_refreshes_pq_key_ttl(real_redis_client):
    # Arrange
    model = PriorityQueueModel(name="refresh_test")
    await model.asave()
    await model.tasks.apush("item", 1.0)

    await real_redis_client.expire(model.key, REDUCED_TTL_SECONDS)
    await real_redis_client.expire(model.tasks.special_key, REDUCED_TTL_SECONDS)
    initial_ttl = await real_redis_client.ttl(model.tasks.special_key)

    # Act
    await model.refresh_ttl_if_needed()

    # Assert
    await assert_ttl_refreshed(
        real_redis_client, initial_ttl, model.tasks.special_key, model.key
    )
