import pytest
import rapyer
from rapyer import RapyerDeleteResult
from rapyer.errors import RapyerModelDoesntExistError, MissingParameterError
from rapyer.fields import RapyerKey
from tests.models.simple_types import StrModel, IntModel
from tests.models.specialized import UserModel


@pytest.mark.asyncio
async def test_rapyer_adelete_many__string_keys_sanity(real_redis_client):
    # Arrange
    str_model = StrModel(name="test_str", description="test description")
    int_model = IntModel(count=42, score=100)
    await rapyer.ainsert(str_model, int_model)

    # Act
    result = await rapyer.adelete_many(str_model.key, int_model.key)

    # Assert
    assert isinstance(result, RapyerDeleteResult)
    assert result.count == 2
    assert result.by_model == {StrModel: 1, IntModel: 1}
    assert await real_redis_client.exists(str_model.key) == 0
    assert await real_redis_client.exists(int_model.key) == 0


@pytest.mark.asyncio
async def test_rapyer_adelete_many__model_instances_sanity(real_redis_client):
    # Arrange
    str_model = StrModel(name="test_str", description="test description")
    int_model = IntModel(count=42, score=100)
    await rapyer.ainsert(str_model, int_model)

    # Act
    result = await rapyer.adelete_many(str_model, int_model)

    # Assert
    assert isinstance(result, RapyerDeleteResult)
    assert result.count == 2
    assert result.by_model == {StrModel: 1, IntModel: 1}
    assert await real_redis_client.exists(str_model.key) == 0
    assert await real_redis_client.exists(int_model.key) == 0


@pytest.mark.asyncio
async def test_rapyer_adelete_many__mixed_keys_and_instances(real_redis_client):
    # Arrange
    str_model = StrModel(name="test_str", description="test description")
    int_model = IntModel(count=42, score=100)
    user_model = UserModel(tags=["tag1", "tag2"])
    await rapyer.ainsert(str_model, int_model, user_model)

    # Act
    result = await rapyer.adelete_many(str_model.key, int_model, user_model.key)

    # Assert
    assert isinstance(result, RapyerDeleteResult)
    assert result.count == 3
    assert result.by_model == {StrModel: 1, IntModel: 1, UserModel: 1}
    assert await real_redis_client.exists(str_model.key) == 0
    assert await real_redis_client.exists(int_model.key) == 0
    assert await real_redis_client.exists(user_model.key) == 0


@pytest.mark.asyncio
async def test_rapyer_adelete_many__multiple_same_class(real_redis_client):
    # Arrange
    user1 = UserModel(tags=["tag1"])
    user2 = UserModel(tags=["tag2"])
    user3 = UserModel(tags=["tag3"])
    await rapyer.ainsert(user1, user2, user3)

    # Act
    result = await rapyer.adelete_many(user1, user2, user3)

    # Assert
    assert isinstance(result, RapyerDeleteResult)
    assert result.count == 3
    assert result.by_model == {UserModel: 3}
    assert await real_redis_client.exists(user1.key) == 0
    assert await real_redis_client.exists(user2.key) == 0
    assert await real_redis_client.exists(user3.key) == 0


@pytest.mark.asyncio
async def test_rapyer_adelete_many__no_args_raises_type_error():
    # Arrange
    # Act & Assert
    with pytest.raises(
        MissingParameterError, match="adelete_many requires at least one argument"
    ):
        await rapyer.adelete_many()


@pytest.mark.asyncio
async def test_rapyer_adelete_many__unknown_class_raises_error():
    # Arrange
    # Act & Assert
    with pytest.raises(RapyerModelDoesntExistError):
        await rapyer.adelete_many(RapyerKey("UnknownClass:some_id"))


@pytest.mark.asyncio
async def test_rapyer_adelete_many__nonexistent_key_silent_skip(real_redis_client):
    # Arrange
    nonexistent_key = RapyerKey("StrModel:nonexistent_key_12345")

    # Act
    result = await rapyer.adelete_many(nonexistent_key)

    # Assert
    assert isinstance(result, RapyerDeleteResult)
    assert result.count == 0
    assert result.by_model == {StrModel: 1}


@pytest.mark.asyncio
async def test_rapyer_adelete_many__stale_model_silent_skip(real_redis_client):
    # Arrange
    user = UserModel(tags=["test"])
    await rapyer.ainsert(user)
    await real_redis_client.delete(user.key)

    # Act
    result = await rapyer.adelete_many(user)

    # Assert
    assert isinstance(result, RapyerDeleteResult)
    assert result.count == 0
    assert result.by_model == {UserModel: 1}


@pytest.mark.asyncio
async def test_rapyer_adelete_many__returns_module_delete_result_type(
    real_redis_client,
):
    # Arrange
    str_model = StrModel(name="test", description="test")
    await rapyer.ainsert(str_model)

    # Act
    result = await rapyer.adelete_many(str_model.key)

    # Assert
    assert isinstance(result, RapyerDeleteResult)
    assert result.count == 1
    assert result.by_model == {StrModel: 1}


@pytest.mark.asyncio
async def test_rapyer_adelete_many__per_model_breakdown_only_counts_deleted(
    real_redis_client,
):
    # Arrange
    str_model1 = StrModel(name="str1", description="test1")
    str_model2 = StrModel(name="str2", description="test2")
    int_model = IntModel(count=42, score=100)
    await rapyer.ainsert(str_model1, str_model2, int_model)
    await real_redis_client.delete(str_model2.key)

    # Act
    result = await rapyer.adelete_many(str_model1.key, str_model2.key, int_model.key)

    # Assert
    assert isinstance(result, RapyerDeleteResult)
    assert result.count == 2
    assert result.by_model == {StrModel: 2, IntModel: 1}
    assert await real_redis_client.exists(str_model1.key) == 0
    assert await real_redis_client.exists(str_model2.key) == 0
    assert await real_redis_client.exists(int_model.key) == 0


@pytest.mark.asyncio
async def test_rapyer_adelete_many__was_commited_true_outside_pipeline(
    real_redis_client,
):
    # Arrange
    str_model = StrModel(name="test", description="test")
    await rapyer.ainsert(str_model)

    # Act
    result = await rapyer.adelete_many(str_model.key)

    # Assert
    assert result.was_committed is True


@pytest.mark.asyncio
async def test_rapyer_adelete_many__was_commited_false_inside_pipeline(
    real_redis_client,
):
    # Arrange
    str_model = StrModel(name="test", description="test")
    await rapyer.ainsert(str_model)

    # Act
    async with rapyer.apipeline():
        result = await rapyer.adelete_many(str_model.key)

    # Assert
    assert result.was_committed is False


@pytest.mark.asyncio
async def test_rapyer_adelete_many__single_redis_transaction_verification(
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
    result = await rapyer.adelete_many(user1, user2, user3)

    # Assert
    final_stats = await real_redis_client.info("commandstats")
    final_del_calls = final_stats.get("cmdstat_del", {}).get("calls", 0)

    del_commands_executed = final_del_calls - initial_del_calls
    assert (
        del_commands_executed == 1
    ), f"Expected 1 DEL command (bulk delete per class), but {del_commands_executed} were executed"

    assert isinstance(result, RapyerDeleteResult)
    assert result.count == 3
    assert await real_redis_client.exists(user1.key) == 0
    assert await real_redis_client.exists(user2.key) == 0
    assert await real_redis_client.exists(user3.key) == 0
