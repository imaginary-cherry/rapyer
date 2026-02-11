import pytest
import rapyer
from rapyer import DeleteResult
from rapyer.errors import UnsupportArgumentTypeError
from rapyer.fields import RapyerKey
from tests.models.index_types import IndexTestModel
from tests.models.specialized import UserModel


@pytest.mark.asyncio
async def test_adelete_many_integration__delete_multiple_models_sanity(
    real_redis_client,
):
    # Arrange
    user1 = UserModel(tags=["tag1"])
    user2 = UserModel(tags=["tag2"])
    user3 = UserModel(tags=["tag3"])
    await rapyer.ainsert(user1, user2, user3)

    # Act
    result = await UserModel.adelete_many(user1, user2.key, user3)

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 3
    assert await real_redis_client.exists(user1.key) == 0
    assert await real_redis_client.exists(user2.key) == 0
    assert await real_redis_client.exists(user3.key) == 0


@pytest.mark.asyncio
async def test_adelete_many_integration__single_redis_transaction_verification(
    real_redis_client,
):
    # Arrange
    user1 = UserModel(tags=["tag1"])
    user2 = UserModel(tags=["tag2"])
    user3 = UserModel(tags=["tag3"])
    await rapyer.ainsert(user1, user2, user3)

    initial_stats = await real_redis_client.info("commandstats")
    initial_del_calls = initial_stats.get("cmdstat_del", {}).get("calls", 0)

    # Act
    result = await UserModel.adelete_many(user1, user2, user3)

    # Assert
    final_stats = await real_redis_client.info("commandstats")
    final_del_calls = final_stats.get("cmdstat_del", {}).get("calls", 0)

    del_commands_executed = final_del_calls - initial_del_calls
    assert (
        del_commands_executed == 1
    ), f"Expected 3 DEL commands (one per key in pipeline), but {del_commands_executed} were executed"

    assert isinstance(result, DeleteResult)
    assert result.count == 3
    assert await real_redis_client.exists(user1.key) == 0
    assert await real_redis_client.exists(user2.key) == 0
    assert await real_redis_client.exists(user3.key) == 0


@pytest.mark.asyncio
async def test_adelete_many__expression_delete_sanity(
    real_redis_client, create_index, inserted_test_models
):
    # Arrange
    IndexTestModel.init_class()
    alice, bob, charlie, david = inserted_test_models

    # Act
    result = await IndexTestModel.adelete_many(IndexTestModel.age > 30)

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 2
    assert await real_redis_client.exists(alice.key) == 1
    assert await real_redis_client.exists(bob.key) == 1
    assert await real_redis_client.exists(charlie.key) == 0
    assert await real_redis_client.exists(david.key) == 0


@pytest.mark.asyncio
async def test_adelete_many__multiple_expressions_combined(
    real_redis_client, create_index, inserted_test_models
):
    # Arrange
    IndexTestModel.init_class()
    alice, bob, charlie, david = inserted_test_models

    # Act
    result = await IndexTestModel.adelete_many(
        IndexTestModel.age >= 30, IndexTestModel.name == "Charlie"
    )

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 1
    assert await real_redis_client.exists(alice.key) == 1
    assert await real_redis_client.exists(bob.key) == 1
    assert await real_redis_client.exists(charlie.key) == 0
    assert await real_redis_client.exists(david.key) == 1


@pytest.mark.asyncio
async def test_adelete_many__expression_no_match_returns_zero(
    real_redis_client, create_index, inserted_test_models
):
    # Arrange
    IndexTestModel.init_class()
    alice, bob, charlie, david = inserted_test_models

    # Act
    result = await IndexTestModel.adelete_many(IndexTestModel.age > 100)

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 0
    assert await real_redis_client.exists(alice.key) == 1
    assert await real_redis_client.exists(bob.key) == 1
    assert await real_redis_client.exists(charlie.key) == 1
    assert await real_redis_client.exists(david.key) == 1


@pytest.mark.asyncio
async def test_adelete_many__no_args_raises_type_error():
    # Arrange
    # Act & Assert
    with pytest.raises(UnsupportArgumentTypeError):
        await IndexTestModel.adelete_many()


@pytest.mark.asyncio
async def test_adelete_many__mixed_expressions_and_keys_raises_type_error(
    real_redis_client, create_index, inserted_test_models
):
    # Arrange
    IndexTestModel.init_class()
    alice, bob, charlie, david = inserted_test_models

    # Act & Assert
    with pytest.raises(UnsupportArgumentTypeError):
        await IndexTestModel.adelete_many(alice, IndexTestModel.age > 30)

    with pytest.raises(UnsupportArgumentTypeError):
        await IndexTestModel.adelete_many(alice.key, IndexTestModel.age > 30)


@pytest.mark.asyncio
async def test_adelete_many__key_auto_prefix(real_redis_client):
    # Arrange
    user = UserModel(tags=["test"])
    await rapyer.ainsert(user)

    # Act
    result = await UserModel.adelete_many(user.pk)

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 1
    assert await real_redis_client.exists(user.key) == 0


@pytest.mark.asyncio
async def test_adelete_many__full_key_no_prefix(real_redis_client):
    # Arrange
    user = UserModel(tags=["test"])
    await rapyer.ainsert(user)

    # Act
    result = await UserModel.adelete_many(user.key)

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 1
    assert await real_redis_client.exists(user.key) == 0


@pytest.mark.asyncio
async def test_adelete_many__missing_key_silent_skip(real_redis_client):
    # Arrange
    # Act
    result = await UserModel.adelete_many(RapyerKey("nonexistent-key"))

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 0


@pytest.mark.asyncio
async def test_adelete_many__stale_model_silent_skip(real_redis_client):
    # Arrange
    user = UserModel(tags=["test"])
    await rapyer.ainsert(user)
    await real_redis_client.delete(user.key)

    # Act
    result = await UserModel.adelete_many(user)

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 0


@pytest.mark.asyncio
async def test_adelete_many__models_and_keys_mixed(real_redis_client):
    # Arrange
    user1 = UserModel(tags=["tag1"])
    user2 = UserModel(tags=["tag2"])
    user3 = UserModel(tags=["tag3"])
    await rapyer.ainsert(user1, user2, user3)

    # Act
    result = await UserModel.adelete_many(user1, user2.key, user3.pk)

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 3
    assert await real_redis_client.exists(user1.key) == 0
    assert await real_redis_client.exists(user2.key) == 0
    assert await real_redis_client.exists(user3.key) == 0


@pytest.mark.asyncio
async def test_adelete_many__returns_delete_result_type(real_redis_client):
    # Arrange
    user = UserModel(tags=["test"])
    await rapyer.ainsert(user)

    # Act
    result = await UserModel.adelete_many(user.key)

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("record_count", [1001, 2500])
async def test_adelete_many__expression_with_cursor_pagination(
    real_redis_client, create_index, record_count
):
    # Arrange
    IndexTestModel.init_class()
    models = [
        IndexTestModel(name=f"user_{i}", age=50, description=f"desc_{i}")
        for i in range(record_count)
    ]
    await IndexTestModel.ainsert(*models)

    # Act
    result = await IndexTestModel.adelete_many(IndexTestModel.age == 50)

    # Assert
    assert isinstance(result, DeleteResult)
    assert result.count == record_count
    for model in models[:5] + models[-5:]:
        assert await real_redis_client.exists(model.key) == 0
