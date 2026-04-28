import pytest

from rapyer.errors.delete import BadDeleteActionError
from tests.models.complex_types import OuterModelWithRedisNested
from tests.models.specialized import UserModel


@pytest.mark.asyncio
async def test_delete_integration__save_verify_exists_delete_verify_removed_sanity(
    real_redis_client,
):
    # Arrange
    user = UserModel(tags=["test_tag_1", "test_tag_2"])
    await user.asave()

    # Verify model exists in Redis
    key_exists_before = await real_redis_client.exists(user.key)
    assert key_exists_before == 1

    model_data = await real_redis_client.json().get(user.key, "$")
    assert model_data is not None
    assert model_data[0]["tags"] == ["test_tag_1", "test_tag_2"]

    # Act
    result = await user.adelete()

    # Assert
    assert result is True
    key_exists_after = await real_redis_client.exists(user.key)
    assert key_exists_after == 0


@pytest.mark.asyncio
async def test_delete_integration__delete_unsaved_model_returns_false_edge_case():
    # Arrange
    user = UserModel(tags=["test_tag_1", "test_tag_2"])
    # Note: not saving the model

    # Act
    result = await user.adelete()

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_delete_integration__delete_nonexistent_model_returns_false_edge_case():
    # Arrange
    nonexistent_key = "UserModel:nonexistent_test_key_12345"

    # Act
    result = await UserModel.adelete_by_key(nonexistent_key)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_delete_integration__try_delete_same_key_twice_first_true_second_false_edge_case(
    real_redis_client,
):
    # Arrange
    user = UserModel(tags=["test_tag"])
    await user.asave()

    # Verify model exists
    assert await real_redis_client.exists(user.key) == 1

    # Act - First deletion
    first_result = await UserModel.adelete_by_key(user.key)

    # Assert first deletion
    assert first_result is True
    assert await real_redis_client.exists(user.key) == 0

    # Act - Second deletion of the same key
    second_result = await UserModel.adelete_by_key(user.key)

    # Assert second deletion
    assert second_result is False


@pytest.mark.asyncio
async def test_delete_integration__call_delete_on_inner_model_raises_runtime_error_edge_case(
    real_redis_client,
):
    # Arrange
    outer_model = OuterModelWithRedisNested()
    await outer_model.asave()

    # Access the inner redis model which should have field_name set
    inner_redis_model = outer_model.container.inner_redis
    assert inner_redis_model.is_inner_model() is True

    # Act & Assert
    with pytest.raises(BadDeleteActionError):
        res = await inner_redis_model.adelete()
