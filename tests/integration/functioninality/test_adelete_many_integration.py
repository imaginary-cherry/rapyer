import pytest

from tests.models.specialized import UserModel


@pytest.mark.asyncio
async def test_adelete_many_integration__delete_multiple_models_sanity(
    real_redis_client,
):
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
    await UserModel.adelete_many(user1, user2.key, user3)

    # Assert
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

    await user1.asave()
    await user2.asave()
    await user3.asave()

    # Get the initial DEL command count from Redis stats
    initial_stats = await real_redis_client.info("commandstats")
    initial_del_calls = initial_stats.get("cmdstat_del", {}).get("calls", 0)

    # Act
    await UserModel.adelete_many(user1, user2, user3)

    # Assert
    # Get final DEL command count from Redis stats
    final_stats = await real_redis_client.info("commandstats")
    final_del_calls = final_stats.get("cmdstat_del", {}).get("calls", 0)

    # Verify exactly 3 DEL commands were executed (one per key in pipeline)
    del_commands_executed = final_del_calls - initial_del_calls
    assert (
        del_commands_executed == 3
    ), f"Expected 3 DEL commands (one per key in pipeline), but {del_commands_executed} were executed"

    # Verify all models are actually deleted
    assert await real_redis_client.exists(user1.key) == 0
    assert await real_redis_client.exists(user2.key) == 0
    assert await real_redis_client.exists(user3.key) == 0
