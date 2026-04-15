import pytest

from tests.integration.conftest import REDUCED_TTL_SECONDS
from tests.models.simple_types import (
    TTL_TEST_SECONDS,
    UserModelWithoutTTL as ModelWithoutTTL,
)


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
async def test_no_ttl_refresh_when_ttl_not_configured__sanity(real_redis_client):
    # Arrange
    model = ModelWithoutTTL(name="leo", age=55)
    await model.asave()

    # Act
    loaded_model = await ModelWithoutTTL.aget(model.key)

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl == -1  # No TTL set
    assert loaded_model.name == "leo"


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
