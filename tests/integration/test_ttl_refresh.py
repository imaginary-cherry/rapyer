import pytest

from tests.integration.conftest import REDUCED_TTL_SECONDS
from tests.models.simple_types import TTL_TEST_SECONDS, TTLRefreshTestModel


@pytest.mark.asyncio
async def test_ttl_refresh_on_pipeline_execute__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    async with model.apipeline():
        model.age += 1

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS


@pytest.mark.asyncio
async def test_ttl_refresh_maintains_original_ttl_value__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl
    assert initial_ttl <= REDUCED_TTL_SECONDS

    # Act - refresh TTL
    await model.aload()

    # Assert - TTL should be reset to original value
    refreshed_ttl = await real_redis_client.ttl(model.key)
    assert refreshed_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < refreshed_ttl <= TTL_TEST_SECONDS


@pytest.mark.asyncio
async def test_refresh_ttl_without_pipeline_executes_real_pipeline(real_redis_client):
    # Arrange - refresh_ttl with can_use_pipeline=False runs pipeline_with_execution for real.
    model = TTLRefreshTestModel(name="x", age=1, score=1.0)
    await model.asave()
    await real_redis_client.expire(model.key, 5)

    # Act
    await model.refresh_ttl_if_needed()

    # Assert
    assert await real_redis_client.ttl(model.key) > 5
