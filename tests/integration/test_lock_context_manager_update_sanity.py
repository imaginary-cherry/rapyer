from typing import List

import pytest
import pytest_asyncio
from pydantic import Field

from rapyer.base import AtomicRedisModel


class LockTestModel(AtomicRedisModel):
    name: str = ""
    value: int = 0
    tags: List[str] = Field(default_factory=list)


@pytest_asyncio.fixture(autouse=True)
async def real_redis_client(redis_client):
    LockTestModel.Meta.redis = redis_client
    yield redis_client
    await redis_client.aclose()


@pytest.mark.asyncio
async def test_lock_context_manager_updates_model_with_new_data_sanity():
    # Arrange
    original_model = LockTestModel(name="test", value=42, tags=["tag1"])
    await original_model.asave()

    # Act
    new_model = await LockTestModel.aget(original_model.key)
    new_model.name = "updated_name"
    new_model.value = 100
    new_model.tags.append("tag2")
    await new_model.asave()

    # Assert
    async with original_model.alock() as locked_model:
        assert locked_model.name == "updated_name" == original_model.name
        assert locked_model.value == 100 == original_model.value
        assert locked_model.tags == ["tag1", "tag2"] == original_model.tags
