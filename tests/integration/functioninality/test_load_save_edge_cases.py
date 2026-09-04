import pytest

from rapyer.errors import KeyNotFound
from tests.models.simple_types import UserModelWithTTL
from tests.models.special_types import GenericRedisSetModel


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


@pytest.mark.asyncio
async def test_aload_missing_special_field_model_raises_key_not_found(
    real_redis_client,
):
    # Arrange - a missing special-field key makes the load pipeline return an empty dump.
    model = GenericRedisSetModel[str]()
    await model.asave()
    assert GenericRedisSetModel[str].contains_sf_field() is True

    # Act
    await real_redis_client.delete(model.key)

    # Assert
    with pytest.raises(KeyNotFound):
        await model.aload()
