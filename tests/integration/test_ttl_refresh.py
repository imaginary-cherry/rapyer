import pytest
import rapyer
from rapyer import AtomicRedisModel
from rapyer.types import RedisDict, RedisFloat, RedisInt, RedisList
from rapyer.types.base import RedisType
from tests.conftest import ttl_no_refresh_test_for, ttl_test_for
from tests.integration.conftest import REDUCED_TTL_SECONDS
from tests.models.complex_types import OuterModelWithRedisNested
from tests.models.simple_types import (
    TTL_TEST_SECONDS,
    USER_TTL,
    TTLRefreshTestModel as ModelWithTTL,
    UserModelWithoutTTL as ModelWithoutTTL,
    TTLRefreshDisabledModel as ModelWithTTLNoRefresh,
    UserModelWithTTL,
)


@ttl_test_for(AtomicRedisModel.aget)
@pytest.mark.asyncio
async def test_ttl_refresh_on_aget__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    loaded_model = await ModelWithTTL.aget(model.key)

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert loaded_model.name == model.name


@ttl_test_for(AtomicRedisModel.aload)
@pytest.mark.asyncio
async def test_ttl_refresh_on_aload__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    await model.aload()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS


@ttl_test_for(AtomicRedisModel.aupdate)
@pytest.mark.asyncio
async def test_ttl_refresh_on_aupdate__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    await model.aupdate(name="updated_name")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert model.name == "updated_name"


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


@ttl_test_for(RedisInt.aincrease)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_int_aincrease__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    await model.age.aincrease(5)

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS


@ttl_test_for(RedisFloat.aincrease)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_float_aincrease__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    new_score = await model.score.aincrease(2.5)

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert new_score == 13.0


@ttl_test_for(RedisList.aappend)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_append__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tags.aappend("tag3")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert "tag3" in model.tags


@ttl_test_for(RedisList.aextend)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_extend__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tags.aextend(["tag3", "tag4"])

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert "tag3" in model.tags and "tag4" in model.tags


@ttl_test_for(RedisList.aclear)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_clear__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tags.aclear()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert model.tags == []


@ttl_test_for(RedisDict.aset_item)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_setitem__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    await model.settings.aset_item("key3", "value3")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert model.settings["key3"] == "value3"


@ttl_test_for(RedisDict.aupdate)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_update__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    await model.settings.aupdate(key3="value3", key4="value4")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert model.settings["key3"] == "value3"


@ttl_test_for(RedisDict.aclear)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_clear__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    await model.settings.aclear()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert model.settings == {}


@ttl_test_for(RedisType.aload)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_type_aload__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    loaded_age = await model.age.aload()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert loaded_age == model.age


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


@ttl_no_refresh_test_for(AtomicRedisModel.aget)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_aget__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    loaded_model = await ModelWithTTLNoRefresh.aget(model.key)

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS
    assert loaded_model.name == model.name


@ttl_no_refresh_test_for(AtomicRedisModel.aload)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_aload__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.aload()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisInt.aincrease)
@ttl_no_refresh_test_for(RedisList.aappend)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_type_operation__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act - perform multiple operations
    await model.age.aincrease(5)
    await model.tags.aappend("tag3")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_test_for(RedisType.asave)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_type_asave__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    model.age = 85
    await model.age.asave()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    loaded_age = await model.age.aload()
    assert loaded_age == 85


@ttl_test_for(AtomicRedisModel.asave)
@pytest.mark.asyncio
async def test_ttl_refresh_on_model_asave__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    model.name = "updated_name"
    await model.asave()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS


@ttl_test_for(RedisList.ainsert)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_ainsert__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tags.ainsert(1, "inserted_tag")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert "inserted_tag" in model.tags


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
async def test_ttl_refresh_on_redis_dict_adel_item__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    await model.settings.adel_item("key1")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert "key1" not in model.settings


@ttl_test_for(RedisDict.apop)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_apop__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    popped_value = await model.settings.apop("key1")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert popped_value == "value1"


@ttl_test_for(RedisDict.apopitem)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_dict_apopitem__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    popped_value = await model.settings.apopitem()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert popped_value is not None


@ttl_test_for(RedisList.apop)
@pytest.mark.asyncio
async def test_ttl_refresh_on_redis_list_apop__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    popped_value = await model.tags.apop()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert popped_value == "tag2"


@ttl_test_for(AtomicRedisModel.afind)
@pytest.mark.asyncio
async def test_ttl_refresh_on_afind__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model = saved_model_with_reduced_ttl.model
    initial_ttl = saved_model_with_reduced_ttl.initial_ttl

    # Act
    found_models = await ModelWithTTL.afind()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl > initial_ttl
    assert TTL_TEST_SECONDS - 2 < final_ttl <= TTL_TEST_SECONDS
    assert len(found_models) >= 1


@ttl_no_refresh_test_for(AtomicRedisModel.afind)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_afind__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await ModelWithTTLNoRefresh.afind()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


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
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    model.name = "updated_name"
    await model.asave()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(AtomicRedisModel.aupdate)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_aupdate__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.aupdate(name="updated_name")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisDict.aclear)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_aclear__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.settings.aclear()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisDict.adel_item)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_adel_item__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.settings.adel_item("key1")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisDict.apop)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_apop__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.settings.apop("key1")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisDict.apopitem)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_apopitem__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.settings.apopitem()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisDict.aset_item)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_aset_item__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.settings.aset_item("key3", "value3")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisDict.aupdate)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_dict_aupdate__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.settings.aupdate(key3="value3", key4="value4")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisFloat.aincrease)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_float_aincrease__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.score.aincrease(2.5)

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisList.aclear)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_list_aclear__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tags.aclear()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisList.aextend)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_list_aextend__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tags.aextend(["tag3", "tag4"])

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisList.ainsert)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_list_ainsert__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tags.ainsert(1, "inserted_tag")

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


@ttl_no_refresh_test_for(RedisList.apop)
@pytest.mark.asyncio
async def test_ttl_no_refresh_when_refresh_ttl_disabled_on_redis_list_apop__sanity(
    real_redis_client, saved_no_refresh_model_with_reduced_ttl
):
    # Arrange
    model = saved_no_refresh_model_with_reduced_ttl.model
    initial_ttl = saved_no_refresh_model_with_reduced_ttl.initial_ttl

    # Act
    await model.tags.apop()

    # Assert
    final_ttl = await real_redis_client.ttl(model.key)
    assert final_ttl <= initial_ttl
    assert 0 < final_ttl <= REDUCED_TTL_SECONDS


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
    outer = OuterModelWithRedisNested()
    await outer.asave()

    # Act & Assert
    with pytest.raises(RuntimeError, match="Can only set TTL from top level model"):
        await outer.container.inner_redis.aset_ttl(100)


@pytest.mark.asyncio
async def test_ttl_refresh_on_rapyer_afind_with_mixed_ttl_classes__sanity(
    real_redis_client, saved_model_with_reduced_ttl
):
    # Arrange
    model_with_ttl = saved_model_with_reduced_ttl.model
    initial_ttl_with = saved_model_with_reduced_ttl.initial_ttl
    user_with_ttl = UserModelWithTTL(name="mixed_ttl", age=25)
    model_without_ttl = ModelWithoutTTL(name="mixed_no_ttl", age=30)
    await rapyer.ainsert(user_with_ttl, model_without_ttl)
    await real_redis_client.expire(user_with_ttl.key, REDUCED_TTL_SECONDS)
    initial_user_ttl = await real_redis_client.ttl(user_with_ttl.key)

    # Act
    found_models = await rapyer.afind(
        model_with_ttl.key, user_with_ttl.key, model_without_ttl.key
    )

    # Assert
    ttl_with = await real_redis_client.ttl(model_with_ttl.key)
    user_ttl_with = await real_redis_client.ttl(user_with_ttl.key)
    ttl_without = await real_redis_client.ttl(model_without_ttl.key)
    assert ttl_with > initial_ttl_with
    assert user_ttl_with > initial_user_ttl
    assert TTL_TEST_SECONDS - 2 < ttl_with <= TTL_TEST_SECONDS
    assert USER_TTL - 2 < user_ttl_with <= USER_TTL
    assert ttl_without == -1  # No TTL set
    assert len(found_models) == 3


@pytest.mark.asyncio
async def test_ttl_on_rapyer_ainsert_with_mixed_ttl_models__sanity(real_redis_client):
    # Arrange
    model_with_ttl = ModelWithTTL(name="rapyer_insert_ttl", age=25)
    user_with_ttl = UserModelWithTTL(name="rapyer_insert_user_ttl", age=30)
    model_without_ttl = ModelWithoutTTL(name="rapyer_insert_no_ttl", age=35)

    # Act
    await rapyer.ainsert(model_with_ttl, user_with_ttl, model_without_ttl)

    # Assert
    ttl_model_with = await real_redis_client.ttl(model_with_ttl.key)
    ttl_user_with = await real_redis_client.ttl(user_with_ttl.key)
    ttl_model_without = await real_redis_client.ttl(model_without_ttl.key)
    assert TTL_TEST_SECONDS - 2 < ttl_model_with <= TTL_TEST_SECONDS
    assert USER_TTL - 2 < ttl_user_with <= USER_TTL
    assert ttl_model_without == -1


@pytest.mark.asyncio
async def test_no_ttl_on_ainsert_when_ttl_not_configured__sanity(real_redis_client):
    # Arrange
    model1 = ModelWithoutTTL(name="insert_no_ttl1", age=25)
    model2 = ModelWithoutTTL(name="insert_no_ttl2", age=30)

    # Act
    await ModelWithoutTTL.ainsert(model1, model2)

    # Assert
    ttl1 = await real_redis_client.ttl(model1.key)
    ttl2 = await real_redis_client.ttl(model2.key)
    assert ttl1 == -1
    assert ttl2 == -1
