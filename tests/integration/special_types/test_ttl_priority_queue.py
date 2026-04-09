import pytest
import pytest_asyncio

from rapyer.types.priority_queue import PriorityQueueItem, RedisPriorityQueue
from tests.conftest import ttl_no_refresh_test_for, ttl_test_for
from tests.integration.conftest import REDUCED_TTL_SECONDS, SavedModelWithReducedTTL
from tests.models.simple_types import TTL_TEST_SECONDS
from tests.models.special_types import (
    PriorityQueueModelBase,
    PriorityQueueTTLModel,
    PriorityQueueTTLNoRefreshModel,
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
    model = PriorityQueueTTLModel(name="pq_ttl_test")
    yield create_pq_model(real_redis_client, model)


@pytest_asyncio.fixture
async def saved_pq_no_refresh_model_with_reduced_ttl(real_redis_client):
    model = PriorityQueueTTLNoRefreshModel(name="pq_no_refresh_test")
    yield create_pq_model(real_redis_client, model)


# --- PQ method TTL refresh tests ---


@ttl_test_for(RedisPriorityQueue.apush)
@pytest.mark.asyncio
async def test_ttl_refresh_on_pq_apush(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tasks.apush("new_item", 0.5)

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_pq_ttl <= TTL_TEST_SECONDS


@ttl_test_for(RedisPriorityQueue.apush_many)
@pytest.mark.asyncio
async def test_ttl_refresh_on_pq_apush_many(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tasks.apush_many(
        [
            PriorityQueueItem(value="a", priority=0.1),
            PriorityQueueItem(value="b", priority=0.2),
        ]
    )

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_pq_ttl <= TTL_TEST_SECONDS


@ttl_test_for(RedisPriorityQueue.apop)
@pytest.mark.asyncio
async def test_ttl_refresh_on_pq_apop(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tasks.apop()

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_pq_ttl <= TTL_TEST_SECONDS


@ttl_test_for(RedisPriorityQueue.aclear)
@pytest.mark.asyncio
async def test_ttl_refresh_on_pq_aclear(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tasks.aclear()

    # Assert
    final_model_ttl = await real_redis_client.ttl(model.key)
    assert final_model_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_model_ttl <= TTL_TEST_SECONDS


@ttl_test_for(RedisPriorityQueue.aremove)
@pytest.mark.asyncio
async def test_ttl_refresh_on_pq_aremove(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tasks.aremove("medium")

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_pq_ttl <= TTL_TEST_SECONDS


# --- PQ method TTL no-refresh tests ---


@ttl_no_refresh_test_for(RedisPriorityQueue.apush)
@pytest.mark.asyncio
async def test_ttl_no_refresh_on_pq_apush(
    real_redis_client,
    saved_pq_no_refresh_model_with_reduced_ttl: SavedModelWithReducedTTL,
):
    # Arrange
    model = saved_pq_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_pq_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tasks.apush("new_item", 0.5)

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl <= initial_ttl
    assert 0 < final_pq_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisPriorityQueue.apush_many)
@pytest.mark.asyncio
async def test_ttl_no_refresh_on_pq_apush_many(
    real_redis_client,
    saved_pq_no_refresh_model_with_reduced_ttl: SavedModelWithReducedTTL,
):
    # Arrange
    model = saved_pq_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_pq_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tasks.apush_many(
        [
            PriorityQueueItem(value="a", priority=0.1),
            PriorityQueueItem(value="b", priority=0.2),
        ]
    )

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl <= initial_ttl
    assert 0 < final_pq_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisPriorityQueue.apop)
@pytest.mark.asyncio
async def test_ttl_no_refresh_on_pq_apop(
    real_redis_client,
    saved_pq_no_refresh_model_with_reduced_ttl: SavedModelWithReducedTTL,
):
    # Arrange
    model = saved_pq_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_pq_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tasks.apop()

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl <= initial_ttl
    assert 0 < final_pq_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisPriorityQueue.aclear)
@pytest.mark.asyncio
async def test_ttl_no_refresh_on_pq_aclear(
    real_redis_client,
    saved_pq_no_refresh_model_with_reduced_ttl: SavedModelWithReducedTTL,
):
    # Arrange
    model = saved_pq_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_pq_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tasks.aclear()

    # Assert
    final_model_ttl = await real_redis_client.ttl(model.key)
    assert final_model_ttl <= initial_ttl
    assert 0 < final_model_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisPriorityQueue.aremove)
@pytest.mark.asyncio
async def test_ttl_no_refresh_on_pq_aremove(
    real_redis_client,
    saved_pq_no_refresh_model_with_reduced_ttl: SavedModelWithReducedTTL,
):
    # Arrange
    model = saved_pq_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_pq_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tasks.aremove("medium")

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl <= initial_ttl
    assert 0 < final_pq_ttl <= REDUCED_TTL_SECONDS


# --- Base model action PQ key TTL tests ---


@pytest.mark.asyncio
async def test_ttl_refresh_pq_key_on_asave(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    model.name = "updated"
    await model.asave()

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_pq_ttl <= TTL_TEST_SECONDS


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
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_pq_ttl <= TTL_TEST_SECONDS


@pytest.mark.asyncio
async def test_ttl_refresh_pq_key_on_aupdate(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    await model.aupdate(name="updated")

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_pq_ttl <= TTL_TEST_SECONDS


@pytest.mark.asyncio
async def test_ttl_refresh_pq_key_on_aget(
    real_redis_client, saved_pq_ttl_model_with_reduced_ttl: SavedModelWithReducedTTL
):
    # Arrange
    model = saved_pq_ttl_model_with_reduced_ttl.model
    initial_ttl = saved_pq_ttl_model_with_reduced_ttl.initial_ttl

    # Act
    await PriorityQueueTTLModel.aget(model.key)

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_pq_ttl <= TTL_TEST_SECONDS


@pytest.mark.asyncio
async def test_ttl_refresh_pq_key_on_afind(real_redis_client):
    # Arrange
    model = PriorityQueueTTLModel(name="find_ttl_test")
    await model.asave()
    await model.tasks.apush("item", 1.0)
    await real_redis_client.expire(model.key, REDUCED_TTL_SECONDS)
    await real_redis_client.expire(model.tasks.special_key, REDUCED_TTL_SECONDS)
    initial_ttl = await real_redis_client.ttl(model.tasks.special_key)

    # Act
    await PriorityQueueTTLModel.afind()

    # Assert
    final_pq_ttl = await real_redis_client.ttl(model.tasks.special_key)
    assert final_pq_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_pq_ttl <= TTL_TEST_SECONDS


@pytest.mark.asyncio
async def test_ttl_pq_key_on_ainsert(real_redis_client):
    # Arrange
    model = PriorityQueueTTLModel(name="insert_ttl_test")

    # Act
    await PriorityQueueTTLModel.ainsert(model)

    # Assert
    model_ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < model_ttl <= TTL_TEST_SECONDS
