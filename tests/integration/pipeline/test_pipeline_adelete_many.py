import pytest

import rapyer
from rapyer import DeleteResult, RapyerDeleteResult
from rapyer.base import apipeline
from tests.models.collection_types import ComprehensiveTestModel
from tests.models.simple_types import StrModel, IntModel


@pytest.mark.asyncio
async def test_pipeline_class_adelete_many__keys_deferred_until_execute(real_redis_client):
    # Arrange
    model1 = ComprehensiveTestModel(name="model1", tags=["a"])
    model2 = ComprehensiveTestModel(name="model2", tags=["b"])
    await model1.asave()
    await model2.asave()

    # Act
    async with apipeline():
        result = await ComprehensiveTestModel.adelete_many(model1, model2)

        key1_exists = await real_redis_client.exists(model1.key)
        key2_exists = await real_redis_client.exists(model2.key)
        assert key1_exists == 1
        assert key2_exists == 1

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 2
    assert await real_redis_client.exists(model1.key) == 0
    assert await real_redis_client.exists(model2.key) == 0


@pytest.mark.asyncio
async def test_pipeline_class_adelete_many__with_string_keys(real_redis_client):
    # Arrange
    model1 = ComprehensiveTestModel(name="model1", tags=["a"])
    model2 = ComprehensiveTestModel(name="model2", tags=["b"])
    await model1.asave()
    await model2.asave()

    # Act
    async with apipeline():
        result = await ComprehensiveTestModel.adelete_many(model1.key, model2.key)

        key1_exists = await real_redis_client.exists(model1.key)
        key2_exists = await real_redis_client.exists(model2.key)
        assert key1_exists == 1
        assert key2_exists == 1

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 2
    assert await real_redis_client.exists(model1.key) == 0
    assert await real_redis_client.exists(model2.key) == 0


@pytest.mark.asyncio
async def test_pipeline_class_adelete_many__mixed_with_other_operations(real_redis_client):
    # Arrange
    model1 = ComprehensiveTestModel(name="model1", tags=["a"])
    model2 = ComprehensiveTestModel(name="model2", tags=["b"])
    model3 = ComprehensiveTestModel(name="model3", tags=["c"])
    await model1.asave()
    await model2.asave()

    # Act
    async with apipeline():
        await model3.asave()
        await ComprehensiveTestModel.adelete_many(model1, model2)

        key1_exists = await real_redis_client.exists(model1.key)
        key2_exists = await real_redis_client.exists(model2.key)
        key3_exists = await real_redis_client.exists(model3.key)
        assert key1_exists == 1
        assert key2_exists == 1
        assert key3_exists == 0

    # Assert
    assert await real_redis_client.exists(model1.key) == 0
    assert await real_redis_client.exists(model2.key) == 0
    assert await real_redis_client.exists(model3.key) == 1


@pytest.mark.asyncio
async def test_pipeline_rapyer_adelete_many__deferred_until_execute(real_redis_client):
    # Arrange
    model1 = StrModel(name="str1")
    model2 = IntModel(count=42)
    await rapyer.ainsert(model1, model2)

    # Act
    async with apipeline():
        result = await rapyer.adelete_many(model1.key, model2.key)

        key1_exists = await real_redis_client.exists(model1.key)
        key2_exists = await real_redis_client.exists(model2.key)
        assert key1_exists == 1
        assert key2_exists == 1

    # Assert
    assert isinstance(result, RapyerDeleteResult)
    assert result.count == 2
    assert result.by_model == {StrModel: 1, IntModel: 1}
    assert await real_redis_client.exists(model1.key) == 0
    assert await real_redis_client.exists(model2.key) == 0


@pytest.mark.asyncio
async def test_pipeline_rapyer_adelete_many__with_model_instances(real_redis_client):
    # Arrange
    model1 = StrModel(name="str1")
    model2 = IntModel(count=42)
    await rapyer.ainsert(model1, model2)

    # Act
    async with apipeline():
        result = await rapyer.adelete_many(model1, model2)

        key1_exists = await real_redis_client.exists(model1.key)
        key2_exists = await real_redis_client.exists(model2.key)
        assert key1_exists == 1
        assert key2_exists == 1

    # Assert
    assert isinstance(result, RapyerDeleteResult)
    assert result.count == 2
    assert result.by_model == {StrModel: 1, IntModel: 1}
    assert await real_redis_client.exists(model1.key) == 0
    assert await real_redis_client.exists(model2.key) == 0


@pytest.mark.asyncio
async def test_pipeline_rapyer_adelete_many__mixed_with_other_operations(real_redis_client):
    # Arrange
    model1 = StrModel(name="str1")
    model2 = StrModel(name="str2")
    model3 = ComprehensiveTestModel(name="new_model", tags=["x"])
    await rapyer.ainsert(model1, model2)

    # Act
    async with apipeline():
        await model3.asave()
        await rapyer.adelete_many(model1, model2)

        key1_exists = await real_redis_client.exists(model1.key)
        key2_exists = await real_redis_client.exists(model2.key)
        key3_exists = await real_redis_client.exists(model3.key)
        assert key1_exists == 1
        assert key2_exists == 1
        assert key3_exists == 0

    # Assert
    assert await real_redis_client.exists(model1.key) == 0
    assert await real_redis_client.exists(model2.key) == 0
    assert await real_redis_client.exists(model3.key) == 1
