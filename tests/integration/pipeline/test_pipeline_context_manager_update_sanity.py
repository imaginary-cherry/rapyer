import pytest

from rapyer.types import RedisStr, RedisInt, RedisList
from tests.models.collection_types import BaseModelDictModel, AnyDictModel
from tests.models.common import Person
from tests.models.functionality_types import LockUpdateTestModel as PipelineTestModel


@pytest.mark.asyncio
async def test_pipeline_context_manager_updates_model_with_new_data_sanity():
    # Arrange
    original_model = PipelineTestModel(name="test", value=42, tags=["tag1"])
    await original_model.asave()

    # Act
    new_model = await PipelineTestModel.aget(original_model.key)
    new_model.name = "updated_name"
    new_model.value = 100
    new_model.tags.append("tag2")
    await new_model.asave()

    # Assert
    async with original_model.apipeline() as pipelined_model:
        assert isinstance(original_model.name, RedisStr)
        assert isinstance(pipelined_model.name, RedisStr)
        assert (
            pipelined_model.name.json_path == original_model.name.json_path == "$.name"
        )
        assert pipelined_model.name == "updated_name" == original_model.name
        assert isinstance(original_model.value, RedisInt)
        assert isinstance(pipelined_model.value, RedisInt)
        assert (
            pipelined_model.value.json_path
            == original_model.value.json_path
            == "$.value"
        )
        assert pipelined_model.value == 100 == original_model.value
        assert isinstance(original_model.tags, RedisList)
        assert isinstance(pipelined_model.tags, RedisList)
        assert (
            pipelined_model.tags.json_path == original_model.tags.json_path == "$.tags"
        )
        assert pipelined_model.tags == ["tag1", "tag2"] == original_model.tags


@pytest.mark.asyncio
async def test_pipeline_context_manager_updates_dict_with_non_redis_type_using_update():
    # Arrange
    original_model = AnyDictModel(
        metadata={"alice": Person(name="Alice", age=30, email="alice@example.com")}
    )
    await original_model.asave()

    # Act
    async with original_model.apipeline() as pipelined_model:
        pipelined_model.metadata.update(
            bob=Person(name="Bob", age=25, email="bob@example.com")
        )

    # Assert
    loaded_model = await AnyDictModel.aget(original_model.key)
    assert loaded_model.metadata == {
        "alice": Person(name="Alice", age=30, email="alice@example.com"),
        "bob": Person(name="Bob", age=25, email="bob@example.com"),
    }
