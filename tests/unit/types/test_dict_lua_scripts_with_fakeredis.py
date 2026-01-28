import pytest

from tests.models.redis_types import DirectRedisDictModel


@pytest.fixture
def setup_fake_redis(fake_redis_client):
    original_redis = DirectRedisDictModel.Meta.redis
    original_is_fake = DirectRedisDictModel.Meta.is_fake_redis
    DirectRedisDictModel.Meta.redis = fake_redis_client
    DirectRedisDictModel.Meta.is_fake_redis = True
    yield
    DirectRedisDictModel.Meta.redis = original_redis
    DirectRedisDictModel.Meta.is_fake_redis = original_is_fake


@pytest.mark.asyncio
async def test_redis_dict_apop_with_fakeredis_sanity(setup_fake_redis):
    # Arrange
    model = DirectRedisDictModel(metadata={"key1": "value1", "key2": "value2"})
    await model.asave()

    # Act
    result = await model.metadata.apop("key1")

    # Assert
    assert result == "value1"
    loaded = await DirectRedisDictModel.aget(model.key)
    assert "key1" not in loaded.metadata
    assert loaded.metadata["key2"] == "value2"


@pytest.mark.asyncio
async def test_redis_dict_apopitem_with_fakeredis_sanity(setup_fake_redis):
    # Arrange
    model = DirectRedisDictModel(metadata={"only_key": "only_value"})
    await model.asave()

    # Act
    result = await model.metadata.apopitem()

    # Assert
    assert result == "only_value"
    loaded = await DirectRedisDictModel.aget(model.key)
    assert len(loaded.metadata) == 0
