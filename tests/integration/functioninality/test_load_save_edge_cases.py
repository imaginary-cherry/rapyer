import pytest

from rapyer.errors.base import KeyNotFound
from tests.models.simple_types import UserModelWithTTL


@pytest.mark.asyncio
async def test_asave_with_ttl_sets_expiration_sanity(real_redis_client):
    # Arrange
    model = UserModelWithTTL(name="Alice", age=30)

    # Act
    await model.asave()

    # Assert - Check TTL is set
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 0
    assert ttl <= 300


@pytest.mark.asyncio
async def test_aload_raises_key_not_found_when_key_missing_edge_case():
    # Arrange
    model = UserModelWithTTL(name="Bob", age=25)

    # Act & Assert - Model was never saved, so aload should raise KeyNotFound
    with pytest.raises(KeyNotFound):
        await model.aload()


@pytest.mark.asyncio
async def test_aload_raises_key_not_found_edge_case(real_redis_client):
    # Arrange
    model = UserModelWithTTL(name="Charlie", age=35)

    # Act & Assert - After deletion, aload should raise KeyNotFound
    with pytest.raises(KeyNotFound):
        await model.aload()
