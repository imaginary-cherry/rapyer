import asyncio

import pytest

from tests.models.simple_types import (
    TTLRefreshTestModel as ModelWithTTL,
    UserModelWithoutTTL as ModelWithoutTTL,
    TTLRefreshDisabledModel as ModelWithTTLNoRefresh,
)


@pytest.mark.asyncio
async def test_ttl_refresh_on_aget__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="john", age=30)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    loaded_model = await ModelWithTTL.aget(model.key)

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5
    assert loaded_model.name == "john"


@pytest.mark.asyncio
async def test_ttl_refresh_on_aload__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="jane", age=28)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    await model.aload()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5


@pytest.mark.asyncio
async def test_ttl_refresh_on_aupdate__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="bob", age=35)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    await model.aupdate(name="robert")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5
    assert model.name == "robert"


@pytest.mark.asyncio
async def test_ttl_refresh_on_pipeline_execute__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="alice", age=40)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    async with model.apipeline():
        model.age += 1

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5


@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_int_aincrease__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="charlie", age=45)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    await model.age.aincrease(5)

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5


@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_float_aincrease__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="dave", score=10.5)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    new_score = await model.score.aincrease(2.5)

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5
    assert new_score == 13.0  # aincrease returns the new value


@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_append__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="eve", tags=["tag1"])
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    await model.tags.aappend("tag2")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5
    assert model.tags == ["tag1", "tag2"]


@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_extend__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="frank", tags=["tag1"])
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    await model.tags.aextend(["tag2", "tag3"])

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5
    assert set(model.tags) == {"tag1", "tag2", "tag3"}


@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_clear__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="grace", tags=["tag1", "tag2"])
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    await model.tags.aclear()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5
    assert model.tags == []


@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_setitem__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="henry", settings={"key1": "value1"})
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    await model.settings.aset_item("key2", "value2")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5
    assert model.settings == {"key1": "value1", "key2": "value2"}


@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_update__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="ivan", settings={"key1": "value1"})
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    await model.settings.aupdate(key2="value2", key3="value3")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5
    assert model.settings == {"key1": "value1", "key2": "value2", "key3": "value3"}


@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_clear__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="julia", settings={"key1": "value1"})
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    await model.settings.aclear()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5
    assert model.settings == {}


@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_type_aload__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="kate", age=50)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    loaded_age = await model.age.aload()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl > 3  # Should be close to 5 since TTL was refreshed
    assert ttl <= 5
    assert loaded_age == 50


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
async def test_ttl_refresh_maintains_original_ttl_value__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="mary", age=60)
    await model.asave()

    # Wait to let TTL decrease
    await asyncio.sleep(2)
    initial_ttl = await real_redis_client.ttl(model.key)
    assert initial_ttl <= 3  # Should be around 3 seconds left

    # Act - refresh TTL
    await model.aload()

    # Assert - TTL should be reset to original value (5)
    refreshed_ttl = await real_redis_client.ttl(model.key)
    assert refreshed_ttl > initial_ttl
    assert refreshed_ttl <= 5
    assert refreshed_ttl > 4  # Should be close to 5


@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_aget__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="nancy", age=65)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    loaded_model = await ModelWithTTLNoRefresh.aget(model.key)

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl <= 4  # Should NOT be refreshed, so should be around 4 or less
    assert ttl > 0  # But still has TTL
    assert loaded_model.name == "nancy"


@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_aload__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="oliver", age=70)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act
    await model.aload()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl <= 4  # Should NOT be refreshed
    assert ttl > 0  # But still has TTL


@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_type_operation__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="paul", age=75, tags=["tag1"])
    await model.asave()

    # Let some time pass
    await asyncio.sleep(1)

    # Act - perform multiple operations
    await model.age.aincrease(5)
    await model.tags.aappend("tag2")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl <= 4  # Should NOT be refreshed
    assert ttl > 0  # But still has TTL
