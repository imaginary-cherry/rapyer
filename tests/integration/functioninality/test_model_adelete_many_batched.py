import pytest

import rapyer
from rapyer import DeleteResult
from rapyer.base import apipeline
from tests.models.index_types import IndexTestModel
from tests.models.specialized import UserModel


@pytest.mark.asyncio
async def test_adelete_many__batched_keys_deletion(real_redis_client):
    # Arrange
    original_max = UserModel.Meta.max_delete_per_transaction
    UserModel.Meta.max_delete_per_transaction = 2
    models = [UserModel(tags=[f"tag_{i}"]) for i in range(5)]
    await rapyer.ainsert(*models)

    # Act
    result = await UserModel.adelete_many(*[m.key for m in models])

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 5
    for model in models:
        assert await real_redis_client.exists(model.key) == 0

    assert result.was_committed

    UserModel.Meta.max_delete_per_transaction = original_max


@pytest.mark.asyncio
async def test_adelete_many__batched_filter_deletion(real_redis_client, create_index):
    # Arrange
    original_max = IndexTestModel.Meta.max_delete_per_transaction
    IndexTestModel.Meta.max_delete_per_transaction = 100
    IndexTestModel.init_class()
    models = [
        IndexTestModel(name=f"user_{i}", age=99, description=f"desc_{i}")
        for i in range(250)
    ]
    await IndexTestModel.ainsert(*models)

    # Act
    result = await IndexTestModel.adelete_many(IndexTestModel.age == 99)

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 250
    for model in models[:5] + models[-5:]:
        assert await real_redis_client.exists(model.key) == 0

    assert result.was_committed

    IndexTestModel.Meta.max_delete_per_transaction = original_max


@pytest.mark.asyncio
async def test_adelete_many__no_batching_when_none(real_redis_client):
    # Arrange
    original_max = UserModel.Meta.max_delete_per_transaction
    UserModel.Meta.max_delete_per_transaction = None
    models = [UserModel(tags=[f"tag_{i}"]) for i in range(10)]
    await rapyer.ainsert(*models)

    # Act
    result = await UserModel.adelete_many(*[m.key for m in models])

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 10
    for model in models:
        assert await real_redis_client.exists(model.key) == 0
    assert result.was_committed
    UserModel.Meta.max_delete_per_transaction = original_max


@pytest.mark.asyncio
async def test_adelete_many__no_match_filter_with_no_batching(
    real_redis_client, create_index, inserted_test_models
):
    # Arrange
    original_max = IndexTestModel.Meta.max_delete_per_transaction
    IndexTestModel.Meta.max_delete_per_transaction = None

    # Act
    result = await IndexTestModel.adelete_many(IndexTestModel.age > 100)

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 0
    for model in inserted_test_models:
        assert await real_redis_client.exists(model.key) == 1

    IndexTestModel.Meta.max_delete_per_transaction = original_max


@pytest.mark.asyncio
async def test_adelete_many__pipeline_context_skips_batching(real_redis_client):
    # Arrange
    original_max = UserModel.Meta.max_delete_per_transaction
    UserModel.Meta.max_delete_per_transaction = 2
    models = [UserModel(tags=[f"tag_{i}"]) for i in range(5)]
    await rapyer.ainsert(*models)

    # Act
    async with apipeline():
        result = await UserModel.adelete_many(*[m.key for m in models])

        for model in models:
            assert await real_redis_client.exists(model.key) == 1

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 5
    for model in models:
        assert await real_redis_client.exists(model.key) == 0
    assert not result.was_committed
    UserModel.Meta.max_delete_per_transaction = original_max
