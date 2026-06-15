import pytest

from tests.models.complex_types import OuterModel
from tests.models.simple_types import UserModelWithTTL


@pytest.mark.asyncio
async def test_base_redis_model_with_ttl__save__check_ttl_set_sanity(real_redis_client):
    # Arrange
    user = UserModelWithTTL(name="john", age=30)

    # Act
    await user.asave()

    # Assert
    ttl = await real_redis_client.ttl(user.key)
    assert ttl > 0
    assert ttl <= 300


@pytest.mark.asyncio
async def test_aset_ttl_on_inner_model_raises(real_redis_client):
    # Coverage: aset_ttl's guard that rejects being called on a nested (inner)
    # model. TTL can only be set from the top-level model.
    # Arrange
    model = OuterModel()
    await model.asave()

    # Act / Assert
    assert model.middle_model.is_inner_model() is True
    with pytest.raises(RuntimeError):
        await model.middle_model.aset_ttl(10)
