import pytest

import rapyer
from rapyer.base import AtomicRedisModel
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from tests.conftest import model_pipeline_test_for, standalone_pipeline_test_for
from tests.models.collection_types import ComprehensiveTestModel
from tests.models.simple_types import (
    TTL_TEST_SECONDS,
    TTLRefreshTestModel,
    UserModelWithoutTTL,
)

TTL_SECONDS = 300


@model_pipeline_test_for(AtomicRedisModel.asave)
@pytest.mark.asyncio
async def test_pipeline_model_asave__model_pipeline__check_atomicity(real_redis_client):
    # Arrange
    model = ComprehensiveTestModel(name="original", counter=10)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.name = "updated"
        redis_model.counter = 99
        await redis_model.asave()

        # Assert - changes not visible during pipeline
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.name == "original"
        assert loaded.counter == 10

    # Assert - changes applied after pipeline
    final = await ComprehensiveTestModel.aget(model.key)
    assert final.name == "updated"
    assert final.counter == 99


@model_pipeline_test_for(AtomicRedisModel.ainsert)
@pytest.mark.asyncio
async def test_pipeline_model_ainsert__model_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    existing_model = ComprehensiveTestModel(name="existing")
    await existing_model.asave()
    new_model = ComprehensiveTestModel(name="inserted")

    # Act
    async with existing_model.apipeline():
        await ComprehensiveTestModel.ainsert(new_model)

        # Assert - new model not visible during pipeline
        exists = await real_redis_client.exists(new_model.key)
        assert exists == 0

    # Assert - new model exists after pipeline
    loaded = await ComprehensiveTestModel.aget(new_model.key)
    assert loaded.name == "inserted"


@standalone_pipeline_test_for(AtomicRedisModel.ainsert)
@pytest.mark.asyncio
async def test_pipeline_model_ainsert__standalone_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    model1 = ComprehensiveTestModel(name="model1")
    model2 = ComprehensiveTestModel(name="model2")

    # Act
    async with rapyer.apipeline():
        await ComprehensiveTestModel.ainsert(model1, model2)

        # Assert - models not visible during pipeline
        exists1 = await real_redis_client.exists(model1.key)
        exists2 = await real_redis_client.exists(model2.key)
        assert exists1 == 0
        assert exists2 == 0

    # Assert - models exist after pipeline
    loaded1 = await ComprehensiveTestModel.aget(model1.key)
    loaded2 = await ComprehensiveTestModel.aget(model2.key)
    assert loaded1.name == "model1"
    assert loaded2.name == "model2"


@standalone_pipeline_test_for(AtomicRedisModel.adelete)
@pytest.mark.asyncio
async def test_pipeline_model_adelete__standalone_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    model = ComprehensiveTestModel(name="to_delete")
    await model.asave()

    # Act
    async with rapyer.apipeline():
        await model.adelete()

        # Assert - model still exists during pipeline
        exists = await real_redis_client.exists(model.key)
        assert exists == 1

    # Assert - model deleted after pipeline
    exists = await real_redis_client.exists(model.key)
    assert exists == 0


@standalone_pipeline_test_for(AtomicRedisModel.adelete_by_key)
@pytest.mark.asyncio
async def test_pipeline_model_adelete_by_key__standalone_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    model = ComprehensiveTestModel(name="to_delete")
    await model.asave()

    # Act
    async with rapyer.apipeline():
        await ComprehensiveTestModel.adelete_by_key(model.key)

        # Assert - model still exists during pipeline
        exists = await real_redis_client.exists(model.key)
        assert exists == 1

    # Assert - model deleted after pipeline
    exists = await real_redis_client.exists(model.key)
    assert exists == 0


@model_pipeline_test_for(AtomicRedisModel.adelete_many)
@pytest.mark.asyncio
async def test_pipeline_model_adelete_many__model_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    model1 = ComprehensiveTestModel(name="model1")
    model2 = ComprehensiveTestModel(name="model2")
    model3 = ComprehensiveTestModel(name="model3")
    await ComprehensiveTestModel.ainsert(model1, model2, model3)

    # Act
    async with model1.apipeline():
        await ComprehensiveTestModel.adelete_many(model2, model3)

        # Assert - models still exist during pipeline
        exists2 = await real_redis_client.exists(model2.key)
        exists3 = await real_redis_client.exists(model3.key)
        assert exists2 == 1
        assert exists3 == 1

    # Assert - models deleted after pipeline
    exists2 = await real_redis_client.exists(model2.key)
    exists3 = await real_redis_client.exists(model3.key)
    assert exists2 == 0
    assert exists3 == 0


@standalone_pipeline_test_for(AtomicRedisModel.aset_ttl)
@pytest.mark.asyncio
async def test_pipeline_model_aset_ttl__standalone_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    model = UserModelWithoutTTL(name="user1", age=25)
    await model.asave()
    assert await real_redis_client.ttl(model.key) == -1

    # Act
    async with rapyer.apipeline():
        await model.aset_ttl(TTL_SECONDS)

        # Assert - TTL not set during pipeline
        ttl_during = await real_redis_client.ttl(model.key)
        assert ttl_during == -1

    # Assert - TTL set after pipeline
    ttl_after = await real_redis_client.ttl(model.key)
    assert 0 < ttl_after <= TTL_SECONDS


@model_pipeline_test_for(RedisInt.aincrease)
@pytest.mark.asyncio
async def test_pipeline_redis_int_aincrease__check_atomicity():
    # Arrange
    model = ComprehensiveTestModel(counter=10)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        await redis_model.counter.aincrease(5)

        # Assert - change not visible during pipeline
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.counter == 10

    # Assert - change applied after pipeline
    final = await ComprehensiveTestModel.aget(model.key)
    assert final.counter == 15


@model_pipeline_test_for(RedisList.insert)
@pytest.mark.asyncio
async def test_pipeline_redis_list_insert__check_atomicity():
    # Arrange
    model = ComprehensiveTestModel(tags=["first", "last"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.tags.insert(1, "middle")

        # Assert - change not visible during pipeline
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.tags == ["first", "last"]

    # Assert - change applied after pipeline
    final = await ComprehensiveTestModel.aget(model.key)
    assert final.tags == ["first", "middle", "last"]


@model_pipeline_test_for(RedisList.clear)
@pytest.mark.asyncio
async def test_pipeline_redis_list_clear__check_atomicity():
    # Arrange
    model = ComprehensiveTestModel(tags=["tag1", "tag2", "tag3"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.tags.clear()

        # Assert - change not visible during pipeline
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.tags == ["tag1", "tag2", "tag3"]

    # Assert - change applied after pipeline
    final = await ComprehensiveTestModel.aget(model.key)
    assert final.tags == []


@model_pipeline_test_for(RedisList.remove_range)
@pytest.mark.asyncio
async def test_pipeline_redis_list_remove_range__check_atomicity():
    # Arrange
    model = ComprehensiveTestModel(tags=["a", "b", "c", "d", "e"])
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.tags.remove_range(1, 3)

        # Assert - change not visible during pipeline
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.tags == ["a", "b", "c", "d", "e"]

    # Assert - change applied after pipeline
    final = await ComprehensiveTestModel.aget(model.key)
    assert final.tags == ["a", "d", "e"]


@model_pipeline_test_for(RedisDict.clear)
@pytest.mark.asyncio
async def test_pipeline_redis_dict_clear__check_atomicity():
    # Arrange
    model = ComprehensiveTestModel(metadata={"key1": "val1", "key2": "val2"})
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.metadata.clear()

        # Assert - change not visible during pipeline
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.metadata == {"key1": "val1", "key2": "val2"}

    # Assert - change applied after pipeline
    final = await ComprehensiveTestModel.aget(model.key)
    assert final.metadata == {}


@standalone_pipeline_test_for(AtomicRedisModel.aduplicate)
@pytest.mark.asyncio
async def test_pipeline_model_aduplicate__standalone_pipeline__check_atomicity():
    # Arrange
    model = ComprehensiveTestModel(name="original", counter=42, tags=["t1"])
    await model.asave()

    # Act
    async with rapyer.apipeline():
        duplicate = await model.aduplicate()

        # Assert - duplicate not visible during pipeline
        assert not await ComprehensiveTestModel.aexists(duplicate.key)

    # Assert - duplicate exists after pipeline with correct values
    loaded = await ComprehensiveTestModel.aget(duplicate.key)
    assert loaded.name == "original"
    assert loaded.counter == 42
    assert loaded.tags == ["t1"]
    assert duplicate.pk != model.pk


@standalone_pipeline_test_for(AtomicRedisModel.aduplicate_many)
@pytest.mark.asyncio
async def test_pipeline_model_aduplicate_many__standalone_pipeline__check_atomicity():
    # Arrange
    model = ComprehensiveTestModel(name="original", counter=42, tags=["t1"])
    await model.asave()

    # Act
    async with rapyer.apipeline():
        duplicates = await model.aduplicate_many(3)

        # Assert - duplicates not visible during pipeline
        for dup in duplicates:
            assert not await ComprehensiveTestModel.aexists(dup.key)

    # Assert - all duplicates exist after pipeline
    for dup in duplicates:
        loaded = await ComprehensiveTestModel.aget(dup.key)
        assert loaded.name == "original"
        assert loaded.counter == 42
        assert loaded.tags == ["t1"]

    # All PKs should be unique
    all_pks = [model.pk] + [d.pk for d in duplicates]
    assert len(set(all_pks)) == 4


@standalone_pipeline_test_for(AtomicRedisModel.aupdate)
@pytest.mark.asyncio
async def test_pipeline_model_aupdate__standalone_pipeline__executes_immediately():
    # Arrange
    model = ComprehensiveTestModel(name="original", counter=10)
    await model.asave()

    # Act - aupdate uses its own internal pipeline, so changes are
    # visible immediately even inside an outer pipeline context
    async with rapyer.apipeline():
        await model.aupdate(name="updated", counter=99)

        # Assert - changes visible during pipeline (aupdate is self-contained)
        loaded = await ComprehensiveTestModel.aget(model.key)
        assert loaded.name == "updated"
        assert loaded.counter == 99

    # Assert - still correct after outer pipeline exits
    final = await ComprehensiveTestModel.aget(model.key)
    assert final.name == "updated"
    assert final.counter == 99


@standalone_pipeline_test_for(AtomicRedisModel.refresh_ttl_if_needed)
@pytest.mark.asyncio
async def test_pipeline_model_refresh_ttl__standalone_pipeline__check_atomicity(
    real_redis_client,
):
    # Arrange
    model = TTLRefreshTestModel(name="ttl_test", age=25)
    await model.asave()
    # Reduce TTL to create a measurable gap
    reduced_ttl = 10
    await real_redis_client.expire(model.key, reduced_ttl)
    ttl_before = await real_redis_client.ttl(model.key)
    assert 0 < ttl_before <= reduced_ttl

    # Act
    async with rapyer.apipeline():
        await model.refresh_ttl_if_needed(can_use_pipeline=True)

        # Assert - TTL not refreshed during pipeline
        ttl_during = await real_redis_client.ttl(model.key)
        assert ttl_during <= reduced_ttl

    # Assert - TTL refreshed after pipeline
    ttl_after = await real_redis_client.ttl(model.key)
    assert ttl_after > reduced_ttl
    assert ttl_after <= TTL_TEST_SECONDS
