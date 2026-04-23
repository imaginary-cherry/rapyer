import pytest

from tests.models.simple_types import UserModelWithTTL


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
