import pytest

from tests.models.simple_types import UserModelWithoutTTL


TTL_SECONDS = 300


@pytest.mark.asyncio
async def test_pipeline_aset_ttl__multiple_models__check_ttl_set_atomically(real_redis_client):
    # Arrange
    models = [
        UserModelWithoutTTL(name="user1", age=25),
        UserModelWithoutTTL(name="user2", age=30),
        UserModelWithoutTTL(name="user3", age=35),
    ]
    await UserModelWithoutTTL.ainsert(*models)

    ttls_before = [await real_redis_client.ttl(model.key) for model in models]
    assert all(ttl == -1 for ttl in ttls_before)

    # Act
    async with models[0].apipeline():
        for model in models:
            await model.aset_ttl(TTL_SECONDS)

        ttls_during = [await real_redis_client.ttl(model.key) for model in models]
        assert all(ttl == -1 for ttl in ttls_during)

    # Assert
    ttls_after = [await real_redis_client.ttl(model.key) for model in models]
    assert all(0 < ttl <= TTL_SECONDS for ttl in ttls_after)
