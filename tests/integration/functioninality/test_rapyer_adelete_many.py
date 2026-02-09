import pytest
import rapyer
from rapyer import ModuleDeleteResult
from rapyer.errors import RapyerModelDoesntExistError
from tests.models.simple_types import StrModel, IntModel
from tests.models.specialized import UserModel


@pytest.mark.asyncio
async def test_rapyer_adelete_many__string_keys_sanity(real_redis_client):
    # Arrange
    str_model = StrModel(name="test_str", description="test description")
    int_model = IntModel(count=42, score=100)
    await str_model.asave()
    await int_model.asave()

    assert await real_redis_client.exists(str_model.key) == 1
    assert await real_redis_client.exists(int_model.key) == 1

    # Act
    result = await rapyer.adelete_many(str_model.key, int_model.key)

    # Assert
    assert isinstance(result, ModuleDeleteResult)
    assert result.count == 2
    assert result.by_model == {"StrModel": 1, "IntModel": 1}
    assert await real_redis_client.exists(str_model.key) == 0
    assert await real_redis_client.exists(int_model.key) == 0


@pytest.mark.asyncio
async def test_rapyer_adelete_many__model_instances_sanity(real_redis_client):
    # Arrange
    str_model = StrModel(name="test_str", description="test description")
    int_model = IntModel(count=42, score=100)
    await str_model.asave()
    await int_model.asave()

    assert await real_redis_client.exists(str_model.key) == 1
    assert await real_redis_client.exists(int_model.key) == 1

    # Act
    result = await rapyer.adelete_many(str_model, int_model)

    # Assert
    assert isinstance(result, ModuleDeleteResult)
    assert result.count == 2
    assert result.by_model == {"StrModel": 1, "IntModel": 1}
    assert await real_redis_client.exists(str_model.key) == 0
    assert await real_redis_client.exists(int_model.key) == 0


@pytest.mark.asyncio
async def test_rapyer_adelete_many__mixed_keys_and_instances(real_redis_client):
    # Arrange
    str_model = StrModel(name="test_str", description="test description")
    int_model = IntModel(count=42, score=100)
    user_model = UserModel(tags=["tag1", "tag2"])
    await str_model.asave()
    await int_model.asave()
    await user_model.asave()

    assert await real_redis_client.exists(str_model.key) == 1
    assert await real_redis_client.exists(int_model.key) == 1
    assert await real_redis_client.exists(user_model.key) == 1

    # Act
    result = await rapyer.adelete_many(str_model.key, int_model, user_model.key)

    # Assert
    assert isinstance(result, ModuleDeleteResult)
    assert result.count == 3
    assert result.by_model == {"StrModel": 1, "IntModel": 1, "UserModel": 1}
    assert await real_redis_client.exists(str_model.key) == 0
    assert await real_redis_client.exists(int_model.key) == 0
    assert await real_redis_client.exists(user_model.key) == 0


@pytest.mark.asyncio
async def test_rapyer_adelete_many__multiple_same_class(real_redis_client):
    # Arrange
    user1 = UserModel(tags=["tag1"])
    user2 = UserModel(tags=["tag2"])
    user3 = UserModel(tags=["tag3"])
    await user1.asave()
    await user2.asave()
    await user3.asave()

    assert await real_redis_client.exists(user1.key) == 1
    assert await real_redis_client.exists(user2.key) == 1
    assert await real_redis_client.exists(user3.key) == 1

    # Act
    result = await rapyer.adelete_many(user1, user2, user3)

    # Assert
    assert isinstance(result, ModuleDeleteResult)
    assert result.count == 3
    assert result.by_model == {"UserModel": 3}
    assert await real_redis_client.exists(user1.key) == 0
    assert await real_redis_client.exists(user2.key) == 0
    assert await real_redis_client.exists(user3.key) == 0


@pytest.mark.asyncio
async def test_rapyer_adelete_many__no_args_raises_type_error():
    # Arrange
    # Act & Assert
    with pytest.raises(TypeError, match="adelete_many requires at least one argument"):
        await rapyer.adelete_many()


@pytest.mark.asyncio
async def test_rapyer_adelete_many__unknown_class_raises_error():
    # Arrange
    # Act & Assert
    with pytest.raises(RapyerModelDoesntExistError):
        await rapyer.adelete_many("UnknownClass:some_id")


@pytest.mark.asyncio
async def test_rapyer_adelete_many__nonexistent_key_silent_skip(real_redis_client):
    # Arrange
    nonexistent_key = "StrModel:nonexistent_key_12345"
    assert await real_redis_client.exists(nonexistent_key) == 0

    # Act
    result = await rapyer.adelete_many(nonexistent_key)

    # Assert
    assert isinstance(result, ModuleDeleteResult)
    assert result.count == 0
    assert result.by_model == {}


@pytest.mark.asyncio
async def test_rapyer_adelete_many__stale_model_silent_skip(real_redis_client):
    # Arrange
    user = UserModel(tags=["test"])
    await user.asave()
    assert await real_redis_client.exists(user.key) == 1
    await real_redis_client.delete(user.key)
    assert await real_redis_client.exists(user.key) == 0

    # Act
    result = await rapyer.adelete_many(user)

    # Assert
    assert isinstance(result, ModuleDeleteResult)
    assert result.count == 0
    assert result.by_model == {}


@pytest.mark.asyncio
async def test_rapyer_adelete_many__returns_module_delete_result_type(real_redis_client):
    # Arrange
    str_model = StrModel(name="test", description="test")
    await str_model.asave()

    # Act
    result = await rapyer.adelete_many(str_model.key)

    # Assert
    assert isinstance(result, ModuleDeleteResult)
    assert result.count == 1
    assert result.by_model == {"StrModel": 1}


@pytest.mark.asyncio
async def test_rapyer_adelete_many__per_model_breakdown_only_counts_deleted(
    real_redis_client,
):
    # Arrange
    str_model1 = StrModel(name="str1", description="test1")
    str_model2 = StrModel(name="str2", description="test2")
    int_model = IntModel(count=42, score=100)
    await str_model1.asave()
    await str_model2.asave()
    await int_model.asave()

    assert await real_redis_client.exists(str_model1.key) == 1
    assert await real_redis_client.exists(str_model2.key) == 1
    assert await real_redis_client.exists(int_model.key) == 1

    await real_redis_client.delete(str_model2.key)
    assert await real_redis_client.exists(str_model2.key) == 0

    # Act
    result = await rapyer.adelete_many(str_model1.key, str_model2.key, int_model.key)

    # Assert
    assert isinstance(result, ModuleDeleteResult)
    assert result.count == 2
    assert result.by_model == {"StrModel": 1, "IntModel": 1}
    assert await real_redis_client.exists(str_model1.key) == 0
    assert await real_redis_client.exists(str_model2.key) == 0
    assert await real_redis_client.exists(int_model.key) == 0
