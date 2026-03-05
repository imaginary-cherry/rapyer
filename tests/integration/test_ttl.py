import pytest
from tests.models.simple_types import UserModelWithoutTTL, UserModelWithTTL


@pytest.mark.asyncio
async def test_base_redis_model_with_ttl__save__check_ttl_set_sanity(real_redis_client):
    # Arrange
    user = UserModelWithTTL(name="john", age=30)

    # Act
    await user.asave()

    # Assert
    ttl = await real_redis_client.ttl(user.key)
    assert ttl > 0
    assert ttl <= 300


@pytest.mark.asyncio
async def test_base_redis_model_without_ttl__save__check_no_ttl_set_sanity(
    real_redis_client,
):
    # Arrange
    user = UserModelWithoutTTL(name="john", age=30)

    # Act
    await user.asave()

    # Assert
    ttl = await real_redis_client.ttl(user.key)
    assert ttl == -1
