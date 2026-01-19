import asyncio

import pytest
from rapyer import AtomicRedisModel
from rapyer.types import RedisDict, RedisFloat, RedisInt, RedisList
from rapyer.types.base import RedisType
from tests.conftest import ttl_no_refresh_test_for, ttl_test_for
from tests.models.simple_types import (
    TTL_TEST_SECONDS,
    TTLRefreshTestModel as ModelWithTTL,
    UserModelWithoutTTL as ModelWithoutTTL,
    TTLRefreshDisabledModel as ModelWithTTLNoRefresh,
)

SLEEP_BEFORE_REFRESH = 1
SLEEP_FOR_TTL_DECREASE = 2


@ttl_test_for(AtomicRedisModel.aget)
@pytest.mark.asyncio
async def test_ttl_refresh_on_aget__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="john", age=30)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    loaded_model = await ModelWithTTL.aget(model.key)

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert loaded_model.name == "john"


@ttl_test_for(AtomicRedisModel.aload)
@pytest.mark.asyncio
async def test_ttl_refresh_on_aload__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="jane", age=28)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.aload()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS


@ttl_test_for(AtomicRedisModel.aupdate)
@pytest.mark.asyncio
async def test_ttl_refresh_on_aupdate__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="bob", age=35)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.aupdate(name="robert")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert model.name == "robert"


@pytest.mark.asyncio
async def test_ttl_refresh_on_pipeline_execute__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="alice", age=40)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    async with model.apipeline():
        model.age += 1

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS


@ttl_test_for(RedisInt.aincrease)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_int_aincrease__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="charlie", age=45)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.age.aincrease(5)

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS


@ttl_test_for(RedisFloat.aincrease)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_float_aincrease__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="dave", score=10.5)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    new_score = await model.score.aincrease(2.5)

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert new_score == 13.0  # aincrease returns the new value


@ttl_test_for(RedisList.aappend)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_append__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="eve", tags=["tag1"])
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.tags.aappend("tag2")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert model.tags == ["tag1", "tag2"]


@ttl_test_for(RedisList.aextend)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_extend__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="frank", tags=["tag1"])
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.tags.aextend(["tag2", "tag3"])

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert set(model.tags) == {"tag1", "tag2", "tag3"}


@ttl_test_for(RedisList.aclear)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_clear__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="grace", tags=["tag1", "tag2"])
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.tags.aclear()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert model.tags == []


@ttl_test_for(RedisDict.aset_item)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_setitem__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="henry", settings={"key1": "value1"})
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.settings.aset_item("key2", "value2")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert model.settings == {"key1": "value1", "key2": "value2"}


@ttl_test_for(RedisDict.aupdate)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_update__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="ivan", settings={"key1": "value1"})
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.settings.aupdate(key2="value2", key3="value3")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert model.settings == {"key1": "value1", "key2": "value2", "key3": "value3"}


@ttl_test_for(RedisDict.aclear)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_clear__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="julia", settings={"key1": "value1"})
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.settings.aclear()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert model.settings == {}


@ttl_test_for(RedisType.aload)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_type_aload__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="kate", age=50)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    loaded_age = await model.age.aload()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
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
    await asyncio.sleep(SLEEP_FOR_TTL_DECREASE)
    initial_ttl = await real_redis_client.ttl(model.key)
    assert initial_ttl <= TTL_TEST_SECONDS - SLEEP_FOR_TTL_DECREASE

    # Act - refresh TTL
    await model.aload()

    # Assert - TTL should be reset to original value
    refreshed_ttl = await real_redis_client.ttl(model.key)
    assert refreshed_ttl > initial_ttl
    assert refreshed_ttl <= TTL_TEST_SECONDS
    assert refreshed_ttl > TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(AtomicRedisModel.aget)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_aget__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="nancy", age=65)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    loaded_model = await ModelWithTTLNoRefresh.aget(model.key)

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    # Should NOT be refreshed, but still has TTL
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH
    assert loaded_model.name == "nancy"


@ttl_no_refresh_test_for(AtomicRedisModel.aload)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_aload__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="oliver", age=70)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.aload()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    # Should NOT be refreshed, but still has TTL
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisInt.aincrease)
@ttl_no_refresh_test_for(RedisList.aappend)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_type_operation__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="paul", age=75, tags=["tag1"])
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act - perform multiple operations
    await model.age.aincrease(5)
    await model.tags.aappend("tag2")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    # Should NOT be refreshed, but still has TTL
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_test_for(RedisType.asave)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_type_asave__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="quinn", age=80)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    model.age = 85
    await model.age.asave()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    loaded_age = await model.age.aload()
    assert loaded_age == 85


@ttl_test_for(AtomicRedisModel.asave)
@pytest.mark.asyncio
async def test_ttl_refresh_on_model_asave__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="rachel", age=90)
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    model.name = "rachel_updated"
    await model.asave()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS


@ttl_test_for(RedisList.ainsert)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_ainsert__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="sam", tags=["tag1", "tag3"])
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.tags.ainsert(1, "tag2")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert model.tags == ["tag1", "tag2", "tag3"]


@ttl_test_for(AtomicRedisModel.ainsert)
@pytest.mark.asyncio
async def test_ttl_on_model_ainsert__sanity(real_redis_client):
    # Arrange
    model1 = ModelWithTTL(name="tom", age=25)
    model2 = ModelWithTTL(name="tim", age=30)

    # Act
    await ModelWithTTL.ainsert(model1, model2)

    # Assert
    ttl1 = await real_redis_client.ttl(model1.key)
    ttl2 = await real_redis_client.ttl(model2.key)
    assert TTL_TEST_SECONDS - 2 < ttl1 <= TTL_TEST_SECONDS
    assert TTL_TEST_SECONDS - 2 < ttl2 <= TTL_TEST_SECONDS


@ttl_test_for(RedisDict.adel_item)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_adel_item__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="uma", settings={"key1": "value1", "key2": "value2"})
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.settings.adel_item("key1")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert model.settings == {"key2": "value2"}


@ttl_test_for(RedisDict.apop)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_apop__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="vera", settings={"key1": "value1", "key2": "value2"})
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    popped_value = await model.settings.apop("key1")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert popped_value == "value1"


@ttl_test_for(RedisDict.apopitem)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_apopitem__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="walt", settings={"key1": "value1"})
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    popped_value = await model.settings.apopitem()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert popped_value == "value1"


@ttl_test_for(RedisList.apop)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_apop__sanity(real_redis_client):
    # Arrange
    model = ModelWithTTL(name="xena", tags=["tag1", "tag2", "tag3"])
    await model.asave()

    # Let some time pass
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    popped_value = await model.tags.apop()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS
    assert popped_value == "tag3"
    assert model.tags == ["tag1", "tag2"]


@ttl_test_for(AtomicRedisModel.afind)
@pytest.mark.asyncio
async def test_ttl_refresh_on_afind__sanity(real_redis_client):
    # Arrange
    model1 = ModelWithTTL(name="yara", age=25)
    model2 = ModelWithTTL(name="zach", age=30)
    await model1.asave()
    await model2.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    found_models = await ModelWithTTL.afind()

    # Assert
    ttl1 = await real_redis_client.ttl(model1.key)
    ttl2 = await real_redis_client.ttl(model2.key)
    assert TTL_TEST_SECONDS - 2 < ttl1 <= TTL_TEST_SECONDS
    assert TTL_TEST_SECONDS - 2 < ttl2 <= TTL_TEST_SECONDS
    assert len(found_models) == 2


@ttl_no_refresh_test_for(AtomicRedisModel.afind)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_afind__sanity(
    real_redis_client,
):
    # Arrange
    model1 = ModelWithTTLNoRefresh(name="amy", age=25)
    model2 = ModelWithTTLNoRefresh(name="ben", age=30)
    await model1.asave()
    await model2.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await ModelWithTTLNoRefresh.afind()

    # Assert
    ttl1 = await real_redis_client.ttl(model1.key)
    ttl2 = await real_redis_client.ttl(model2.key)
    assert 0 < ttl1 <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH
    assert 0 < ttl2 <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(AtomicRedisModel.ainsert)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_ainsert__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="carl", age=35)

    # Act
    await ModelWithTTLNoRefresh.ainsert(model)

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert ttl <= TTL_TEST_SECONDS
    assert ttl > 0


@ttl_no_refresh_test_for(AtomicRedisModel.asave)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_asave__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="dana", age=40)
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    model.name = "dana_updated"
    await model.asave()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(AtomicRedisModel.aupdate)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_aupdate__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="evan", age=45)
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.aupdate(name="evan_updated")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisDict.aclear)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_aclear__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="fay", settings={"key1": "value1"})
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.settings.aclear()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisDict.adel_item)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_adel_item__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(
        name="gus", settings={"key1": "value1", "key2": "value2"}
    )
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.settings.adel_item("key1")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisDict.apop)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_apop__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(
        name="hal", settings={"key1": "value1", "key2": "value2"}
    )
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.settings.apop("key1")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisDict.apopitem)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_apopitem__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="ivy", settings={"key1": "value1"})
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.settings.apopitem()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisDict.aset_item)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_aset_item__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="jake", settings={"key1": "value1"})
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.settings.aset_item("key2", "value2")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisDict.aupdate)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_aupdate__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="kate", settings={"key1": "value1"})
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.settings.aupdate(key2="value2", key3="value3")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisFloat.aincrease)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_float_aincrease__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="leo", score=10.5)
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.score.aincrease(2.5)

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisList.aclear)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_list_aclear__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="mia", tags=["tag1", "tag2"])
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.tags.aclear()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisList.aextend)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_list_aextend__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="nate", tags=["tag1"])
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.tags.aextend(["tag2", "tag3"])

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisList.ainsert)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_list_ainsert__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="olive", tags=["tag1", "tag3"])
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.tags.ainsert(1, "tag2")

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@ttl_no_refresh_test_for(RedisList.apop)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_list_apop__sanity(
    real_redis_client,
):
    # Arrange
    model = ModelWithTTLNoRefresh(name="pete", tags=["tag1", "tag2", "tag3"])
    await model.asave()
    await asyncio.sleep(SLEEP_BEFORE_REFRESH)

    # Act
    await model.tags.apop()

    # Assert
    ttl = await real_redis_client.ttl(model.key)
    assert 0 < ttl <= TTL_TEST_SECONDS - SLEEP_BEFORE_REFRESH


@pytest.mark.parametrize(
    ["new_ttl"],
    [
        [100],  # Extend TTL (longer than TTL_TEST_SECONDS=24)
        [5],  # Shorten TTL (shorter than TTL_TEST_SECONDS=24)
    ],
)
@pytest.mark.asyncio
async def test_aset_ttl__sanity(real_redis_client, new_ttl):
    # Arrange
    model = ModelWithTTL(name="test_aset_ttl", age=25)
    await model.asave()

    # Act
    await model.aset_ttl(new_ttl)

    # Assert
    actual_ttl = await real_redis_client.ttl(model.key)
    assert new_ttl - 2 < actual_ttl <= new_ttl


@pytest.mark.asyncio
async def test_aset_ttl_on_inner_model__edge_case():
    # Arrange
    from tests.models.complex_types import OuterModelWithRedisNested

    outer = OuterModelWithRedisNested()
    await outer.asave()

    # Act & Assert
    with pytest.raises(RuntimeError, match="Can only set TTL from top level model"):
        await outer.container.inner_redis.aset_ttl(100)
