import pytest
from tests.models.complex_types import (
    ContainerModel,
    InnerMostModel,
    InnerRedisModel,
    MiddleModel,
    OuterModel,
    OuterModelWithRedisNested,
)
from tests.models.inheritance_types import StrictMixedInheritanceModel


@pytest.mark.asyncio
async def test_nested_model_deep_list_append_sanity():
    # Arrange
    outer = OuterModel()
    await outer.asave()

    # Act
    await outer.middle_model.inner_model.lst.aappend("deep_item")

    # Assert
    assert "deep_item" in outer.middle_model.inner_model.lst
    assert len(outer.middle_model.inner_model.lst) == 1

    outer.middle_model.inner_model.lst.clear()
    outer.middle_model.inner_model.lst = (
        await outer.middle_model.inner_model.lst.aload()
    )

    assert outer.middle_model.inner_model.lst == ["deep_item"]


@pytest.mark.asyncio
async def test_nested_model_deep_list_extend_sanity():
    # Arrange
    outer = OuterModel()
    await outer.asave()
    test_items = ["item1", "item2", "item3"]

    # Act
    await outer.middle_model.inner_model.lst.aextend(test_items)

    # Assert
    assert all(item in outer.middle_model.inner_model.lst for item in test_items)
    assert len(outer.middle_model.inner_model.lst) == 3

    outer.middle_model.inner_model.lst.clear()
    outer.middle_model.inner_model.lst = (
        await outer.middle_model.inner_model.lst.aload()
    )
    assert outer.middle_model.inner_model.lst == test_items


@pytest.mark.asyncio
async def test_nested_model_middle_list_operations_sanity():
    # Arrange
    outer = OuterModel()
    await outer.asave()
    test_tags = ["tag1", "tag2"]

    # Act
    await outer.middle_model.tags.aextend(test_tags)
    await outer.middle_model.tags.ainsert(1, "inserted_tag")

    # Assert
    assert "inserted_tag" in outer.middle_model.tags
    assert len(outer.middle_model.tags) == 3

    outer.middle_model.tags.clear()
    outer.middle_model.tags = await outer.middle_model.tags.aload()

    assert outer.middle_model.tags == ["tag1", "inserted_tag", "tag2"]


@pytest.mark.asyncio
async def test_nested_model_middle_dict_operations_sanity():
    # Arrange
    outer = OuterModel()
    await outer.asave()
    test_metadata = {"key1": "value1", "key2": "value2"}

    # Act
    await outer.middle_model.metadata.aupdate(**test_metadata)

    # Assert
    assert outer.middle_model.metadata["key1"] == "value1"
    assert outer.middle_model.metadata["key2"] == "value2"
    assert len(outer.middle_model.metadata) == 2

    outer.middle_model.metadata.clear()
    outer.middle_model.metadata = await outer.middle_model.metadata.aload()

    assert outer.middle_model.metadata == test_metadata


@pytest.mark.asyncio
async def test_nested_model_outer_level_operations_sanity():
    # Arrange
    outer = OuterModel()
    await outer.asave()
    test_user_data = {"user1": 100, "user2": 200}
    test_items = [1, 2, 3]

    # Act
    await outer.user_data.aupdate(**test_user_data)
    await outer.items.aextend(test_items)

    # Assert
    assert outer.user_data["user1"] == 100
    assert len(outer.items) == 3

    outer.user_data.clear()
    outer.items.clear()
    outer.user_data = await outer.user_data.aload()
    outer.items = await outer.items.aload()

    assert outer.user_data == test_user_data
    assert outer.items == test_items


@pytest.mark.parametrize(
    "test_values", [["param1", "param2"], ["a", "b", "c"], ["single"]]
)
@pytest.mark.asyncio
async def test_nested_model_deep_list_multiple_operations_sanity(test_values):
    # Arrange
    outer = OuterModel()
    await outer.asave()

    # Act
    await outer.middle_model.inner_model.lst.aextend(test_values)
    await outer.middle_model.inner_model.lst.aappend("extra")
    popped = await outer.middle_model.inner_model.lst.apop()

    # Assert
    assert popped == "extra" or popped == '"extra"'  # Handle JSON serialization
    assert len(outer.middle_model.inner_model.lst) == len(test_values)
    assert all(val in outer.middle_model.inner_model.lst for val in test_values)

    outer.middle_model.inner_model.lst.clear()
    outer.middle_model.inner_model.lst = (
        await outer.middle_model.inner_model.lst.aload()
    )

    assert outer.middle_model.inner_model.lst == test_values


@pytest.mark.asyncio
async def test_nested_model_persistence_across_instances_sanity():
    # Arrange
    outer1 = OuterModel()
    await outer1.asave()

    # Act
    await outer1.middle_model.inner_model.lst.aappend("persistent_item")
    await outer1.middle_model.tags.aappend("persistent_tag")

    # Create new instance with same pk
    outer2 = OuterModel()
    outer2.pk = outer1.pk
    outer2.middle_model.inner_model.lst = (
        await outer2.middle_model.inner_model.lst.aload()
    )
    outer2.middle_model.tags = await outer2.middle_model.tags.aload()

    # Assert
    assert "persistent_item" in outer2.middle_model.inner_model.lst
    assert "persistent_tag" in outer2.middle_model.tags


@pytest.mark.asyncio
async def test_nested_model_clear_operations_edge_case(real_redis_client):
    # Arrange
    outer = OuterModel()
    await outer.asave()

    await outer.middle_model.inner_model.lst.aextend(["item1", "item2"])
    await outer.middle_model.metadata.aupdate(key1="value1", key2="value2")

    # Act
    await outer.middle_model.inner_model.lst.aclear()
    await outer.middle_model.metadata.aclear()

    # Assert
    assert len(outer.middle_model.inner_model.lst) == 0
    assert len(outer.middle_model.metadata) == 0

    redis_list_data = await real_redis_client.json().get(
        outer.key, outer.middle_model.inner_model.lst.json_path
    )
    redis_dict_data = await real_redis_client.json().get(
        outer.key, outer.middle_model.metadata.json_path
    )
    assert redis_list_data is None or redis_list_data == [] or redis_list_data[0] == []
    assert (
        redis_dict_data is None
        or redis_dict_data == []
        or (
            isinstance(redis_dict_data, list)
            and len(redis_dict_data) > 0
            and redis_dict_data[0] == {}
        )
    )


@pytest.mark.asyncio
async def test_nested_model_mixed_operations_on_different_levels_edge_case():
    # Arrange
    outer = OuterModel()
    await outer.asave()

    # Act
    await outer.items.aappend(10)
    await outer.middle_model.tags.aappend("middle_tag")
    await outer.middle_model.inner_model.lst.aappend("deep_item")
    await outer.user_data.aset_item("count", 5)
    await outer.middle_model.metadata.aset_item("status", "active")

    # Assert
    assert 10 in outer.items
    assert "middle_tag" in outer.middle_model.tags
    assert "deep_item" in outer.middle_model.inner_model.lst
    assert outer.user_data["count"] == 5
    assert outer.middle_model.metadata["status"] == "active"

    outer.items.clear()
    outer.middle_model.tags.clear()
    outer.middle_model.inner_model.lst.clear()
    outer.user_data.clear()
    outer.middle_model.metadata.clear()

    outer.items = await outer.items.aload()
    outer.middle_model.tags = await outer.middle_model.tags.aload()
    outer.middle_model.inner_model.lst = (
        await outer.middle_model.inner_model.lst.aload()
    )
    outer.user_data = await outer.user_data.aload()
    outer.middle_model.metadata = await outer.middle_model.metadata.aload()

    assert outer.items == [10]
    assert outer.middle_model.tags == ["middle_tag"]
    assert outer.middle_model.inner_model.lst == ["deep_item"]
    assert outer.user_data == {"count": 5}
    assert outer.middle_model.metadata == {"status": "active"}


@pytest.mark.asyncio
async def test_nested_model_load_operations_after_external_changes_edge_case(
    real_redis_client,
):
    # Arrange
    outer = OuterModel()
    await outer.asave()

    # Act - simulate external Redis changes
    await real_redis_client.json().arrappend(
        outer.key, outer.middle_model.inner_model.lst.json_path, "external_item"
    )
    await real_redis_client.json().set(
        outer.key,
        f"{outer.middle_model.metadata.json_path}.external_key",
        '"external_value"',
    )

    # Load changes
    outer.middle_model.inner_model.lst = (
        await outer.middle_model.inner_model.lst.aload()
    )
    outer.middle_model.metadata = await outer.middle_model.metadata.aload()

    # Assert
    assert "external_item" in outer.middle_model.inner_model.lst
    external_value = outer.middle_model.metadata.get("external_key")
    assert external_value == "external_value" or external_value == '"external_value"'


@pytest.mark.asyncio
async def test_nested_model_with_initial_list_data_update_sanity():
    # Arrange
    middle_model = MiddleModel(tags=["initial_tag1", "initial_tag2"])
    outer = OuterModel(items=[100, 200], middle_model=middle_model)
    await outer.asave()

    # Act
    await outer.items.aappend(300)
    await outer.middle_model.tags.ainsert(1, "inserted_tag")

    # Assert
    assert 300 in outer.items
    assert "inserted_tag" in outer.middle_model.tags
    assert len(outer.items) == 3
    assert len(outer.middle_model.tags) == 3

    outer.items.clear()
    outer.middle_model.tags.clear()
    loaded = await outer.aload()

    assert loaded.items == [100, 200, 300]
    assert loaded.middle_model.tags == ["initial_tag1", "inserted_tag", "initial_tag2"]


@pytest.mark.asyncio
async def test_nested_model_with_initial_dict_data_update_sanity():
    # Arrange
    middle_model = MiddleModel(metadata={"env": "test", "version": "1.0"})
    outer = OuterModel(
        user_data={"initial_user": 50, "another_user": 75}, middle_model=middle_model
    )
    await outer.asave()

    # Act
    await outer.user_data.aset_item("new_user", 125)
    await outer.middle_model.metadata.aupdate(status="active", build="123")

    # Assert
    assert outer.user_data["new_user"] == 125
    assert outer.middle_model.metadata["status"] == "active"
    assert len(outer.user_data) == 3
    assert len(outer.middle_model.metadata) == 4

    outer.user_data.clear()
    outer.middle_model.metadata.clear()
    outer = await outer.aload()

    expected_user_data = {"initial_user": 50, "another_user": 75, "new_user": 125}
    expected_metadata = {
        "env": "test",
        "version": "1.0",
        "status": "active",
        "build": "123",
    }
    assert outer.user_data == expected_user_data
    assert outer.middle_model.metadata == expected_metadata


@pytest.mark.asyncio
async def test_nested_model_with_initial_deep_data_update_sanity():
    # Arrange
    inner_model = InnerMostModel(lst=["deep1", "deep2"], counter=10)
    middle_model = MiddleModel(inner_model=inner_model)
    outer = OuterModel(middle_model=middle_model)
    await outer.asave()

    # Act
    await outer.middle_model.inner_model.lst.aextend(["deep3", "deep4"])
    outer.middle_model.inner_model.counter = 25
    await outer.middle_model.inner_model.counter.asave()

    # Assert
    assert "deep3" in outer.middle_model.inner_model.lst
    assert "deep4" in outer.middle_model.inner_model.lst
    assert len(outer.middle_model.inner_model.lst) == 4
    assert outer.middle_model.inner_model.counter == 25

    outer.middle_model.inner_model.lst.clear()
    outer = await outer.aload()

    assert outer.middle_model.inner_model.lst == ["deep1", "deep2", "deep3", "deep4"]
    assert outer.middle_model.inner_model.counter == 25


@pytest.mark.asyncio
async def test_nested_model_with_mixed_initial_data_update_sanity():
    # Arrange
    inner_model = InnerMostModel(lst=["inner1"])
    middle_model = MiddleModel(
        inner_model=inner_model, tags=["tag1"], metadata={"initial": "data"}
    )
    outer = OuterModel(
        items=[1, 2], user_data={"existing": 100}, middle_model=middle_model
    )
    await outer.asave()

    # Act
    await outer.items.aextend([3, 4])
    await outer.user_data.aupdate(new_key=200, another=300)
    await outer.middle_model.tags.aappend("tag2")
    await outer.middle_model.metadata.aset_item("updated", "value")
    await outer.middle_model.inner_model.lst.ainsert(0, "inner0")

    # Assert
    assert len(outer.items) == 4
    assert len(outer.user_data) == 3
    assert len(outer.middle_model.tags) == 2
    assert len(outer.middle_model.metadata) == 2
    assert len(outer.middle_model.inner_model.lst) == 2

    outer.items.clear()
    outer.user_data.clear()
    outer.middle_model.tags.clear()
    outer.middle_model.metadata.clear()
    outer.middle_model.inner_model.lst.clear()

    outer = await outer.aload()

    assert outer.items == [1, 2, 3, 4]
    assert outer.user_data == {"existing": 100, "new_key": 200, "another": 300}
    assert outer.middle_model.tags == ["tag1", "tag2"]
    assert outer.middle_model.metadata == {"initial": "data", "updated": "value"}
    assert outer.middle_model.inner_model.lst == ["inner0", "inner1"]


@pytest.mark.asyncio
async def test_nested_model_with_redis_inner_model_basic_operations_sanity():
    # Arrange
    outer = OuterModelWithRedisNested()
    await outer.asave()

    # Act
    await outer.container.inner_redis.tags.aappend("redis_tag")
    await outer.container.inner_redis.metadata.aset_item("key1", "value1")
    await outer.outer_data.aextend([1, 2, 3])

    # Assert
    assert "redis_tag" in outer.container.inner_redis.tags
    assert outer.container.inner_redis.metadata["key1"] == "value1"
    assert len(outer.outer_data) == 3

    outer.container.inner_redis.tags.clear()
    outer.container.inner_redis.metadata.clear()
    outer.outer_data.clear()
    outer.container.inner_redis.tags = await outer.container.inner_redis.tags.aload()
    outer.container.inner_redis.metadata = (
        await outer.container.inner_redis.metadata.aload()
    )
    outer.outer_data = await outer.outer_data.aload()

    assert outer.container.inner_redis.tags == ["redis_tag"]
    assert outer.container.inner_redis.metadata == {"key1": "value1"}
    assert outer.outer_data == [1, 2, 3]


@pytest.mark.asyncio
async def test_nested_model_with_redis_inner_model_counter_update_sanity():
    # Arrange
    outer = OuterModelWithRedisNested()
    await outer.asave()

    # Act
    outer.container.inner_redis.counter = 42
    await outer.asave()

    # Assert
    assert outer.container.inner_redis.counter == 42

    new_outer = await OuterModelWithRedisNested.aget(outer.key)

    assert new_outer.container.inner_redis.counter == 42


@pytest.mark.asyncio
async def test_nested_model_with_redis_inner_model_persistence_sanity():
    # Arrange
    outer1 = OuterModelWithRedisNested()
    await outer1.asave()

    # Act
    await outer1.container.inner_redis.tags.aextend(["tag1", "tag2"])
    await outer1.container.inner_redis.metadata.aupdate(env="test", version="1.0")
    await outer1.outer_data.aappend(100)

    # Create new instance with same pk
    outer2 = OuterModelWithRedisNested()
    outer2.pk = outer1.pk
    outer2.container.inner_redis.tags = await outer2.container.inner_redis.tags.aload()
    outer2.container.inner_redis.metadata = (
        await outer2.container.inner_redis.metadata.aload()
    )
    outer2.outer_data = await outer2.outer_data.aload()

    # Assert
    assert outer2.container.inner_redis.tags == ["tag1", "tag2"]
    assert outer2.container.inner_redis.metadata == {"env": "test", "version": "1.0"}
    assert outer2.outer_data == [100]


@pytest.mark.parametrize(
    "tag_sets", [["redis1", "redis2"], ["a", "b", "c"], ["single"]]
)
@pytest.mark.asyncio
async def test_nested_model_with_redis_inner_model_parameterized_operations_sanity(
    tag_sets,
):
    # Arrange
    outer = OuterModelWithRedisNested()
    await outer.asave()

    # Act
    await outer.container.inner_redis.tags.aextend(tag_sets)
    first_tag = await outer.container.inner_redis.tags.apop(0)

    # Assert
    assert first_tag == tag_sets[0] or first_tag == f'"{tag_sets[0]}"'
    assert len(outer.container.inner_redis.tags) == len(tag_sets) - 1

    outer.container.inner_redis.tags.clear()
    outer.container.inner_redis.tags = await outer.container.inner_redis.tags.aload()

    assert outer.container.inner_redis.tags == tag_sets[1:]


@pytest.mark.asyncio
async def test_nested_model_with_redis_inner_model_mixed_operations_edge_case():
    # Arrange
    outer = OuterModelWithRedisNested()
    await outer.asave()

    # Act
    await outer.container.inner_redis.tags.aappend("first_tag")
    await outer.container.inner_redis.metadata.aset_item("status", "active")
    await outer.outer_data.aextend([10, 20])
    outer.container.inner_redis.counter = 15
    outer.container.description = "updated"
    await outer.asave()

    # Assert
    assert "first_tag" in outer.container.inner_redis.tags
    assert outer.container.inner_redis.metadata["status"] == "active"
    assert outer.outer_data == [10, 20]
    assert outer.container.inner_redis.counter == 15
    assert outer.container.description == "updated"

    outer.container.inner_redis.tags.clear()
    outer.container.inner_redis.metadata.clear()
    outer.outer_data.clear()
    outer = await OuterModelWithRedisNested.aget(outer.key)

    assert outer.container.inner_redis.tags == ["first_tag"]
    assert outer.container.inner_redis.metadata == {"status": "active"}
    assert outer.outer_data == [10, 20]
    assert outer.container.inner_redis.counter == 15
    assert outer.container.description == "updated"


@pytest.mark.asyncio
async def test_nested_model_with_redis_inner_model_clear_operations_edge_case(
    real_redis_client,
):
    # Arrange
    outer = OuterModelWithRedisNested()
    await outer.asave()

    await outer.container.inner_redis.tags.aextend(["tag1", "tag2"])
    await outer.container.inner_redis.metadata.aupdate(key1="value1", key2="value2")

    # Act
    await outer.container.inner_redis.tags.aclear()
    await outer.container.inner_redis.metadata.aclear()

    # Assert
    assert len(outer.container.inner_redis.tags) == 0
    assert len(outer.container.inner_redis.metadata) == 0

    redis_tags_data = await real_redis_client.json().get(
        outer.key, outer.container.inner_redis.tags.json_path
    )
    redis_metadata_data = await real_redis_client.json().get(
        outer.key, outer.container.inner_redis.metadata.json_path
    )
    assert redis_tags_data is None or redis_tags_data == [] or redis_tags_data[0] == []
    assert (
        redis_metadata_data is None
        or redis_metadata_data == []
        or (
            isinstance(redis_metadata_data, list)
            and len(redis_metadata_data) > 0
            and redis_metadata_data[0] == {}
        )
    )


@pytest.mark.asyncio
async def test_nested_model_with_redis_inner_model_with_initial_data_sanity():
    # Arrange
    inner_redis = InnerRedisModel(
        tags=["initial_tag"], metadata={"env": "test"}, counter=5
    )
    container = ContainerModel(inner_redis=inner_redis, description="test_container")
    outer = OuterModelWithRedisNested(container=container, outer_data=[100])
    await outer.asave()

    # Act
    await outer.container.inner_redis.tags.aappend("new_tag")
    await outer.container.inner_redis.metadata.aset_item("version", "1.0")
    await outer.outer_data.aappend(200)

    # Assert
    assert "new_tag" in outer.container.inner_redis.tags
    assert outer.container.inner_redis.metadata["version"] == "1.0"
    assert 200 in outer.outer_data
    assert len(outer.container.inner_redis.tags) == 2
    assert len(outer.container.inner_redis.metadata) == 2
    assert len(outer.outer_data) == 2

    outer.container.inner_redis.tags.clear()
    outer.container.inner_redis.metadata.clear()
    outer.outer_data.clear()
    outer = await OuterModelWithRedisNested.aget(outer.key)

    assert outer.container.inner_redis.tags == ["initial_tag", "new_tag"]
    assert outer.container.inner_redis.metadata == {"env": "test", "version": "1.0"}
    assert outer.outer_data == [100, 200]
    assert outer.container.inner_redis.counter == 5
    assert outer.container.description == "test_container"


@pytest.mark.asyncio
async def test_nested_model_create_inner_save_load_sanity():
    # Arrange
    outer = OuterModel()

    # Act
    new_inner = InnerMostModel(lst=["item1", "item2"], counter=42)
    new_middle = MiddleModel(
        inner_model=new_inner,
        tags=["tag1", "tag2"],
        metadata={"env": "test", "version": "1.0"},
    )
    outer.middle_model = new_middle
    outer.user_data = {"user1": 100, "user2": 200}
    outer.items = [10, 20, 30]
    await outer.asave()

    # Assert
    loaded_outer = await OuterModel.aget(outer.key)

    assert loaded_outer.middle_model.inner_model.lst == ["item1", "item2"]
    assert loaded_outer.middle_model.inner_model.counter == 42
    assert loaded_outer.middle_model.tags == ["tag1", "tag2"]
    assert loaded_outer.middle_model.metadata == {"env": "test", "version": "1.0"}
    assert loaded_outer.user_data == {"user1": 100, "user2": 200}
    assert loaded_outer.items == [10, 20, 30]


@pytest.mark.asyncio
async def test_strict_mixed_inheritance_non_pydantic_fields_not_persisted_sanity(
    real_redis_client,
):
    # Arrange
    model = StrictMixedInheritanceModel(redis_data="custom_data", number=456)

    # Act
    await model.asave()

    # Assert
    # Check that non-pydantic fields exist in memory
    assert hasattr(model, "non_pydantic_field")
    assert hasattr(model, "another_field")
    assert hasattr(model, "temp_data")
    assert model.non_pydantic_field == "should_not_persist"
    assert model.another_field == 999
    assert model.temp_data == {"key": "value"}

    # Load directly from Redis using the client to check what's actually stored
    redis_data = await real_redis_client.json().get(model.key, "$")
    stored_data = redis_data[0]

    # Assert pydantic fields ARE stored in Redis
    assert "redis_data" in stored_data
    assert "number" in stored_data
    assert stored_data["redis_data"] == "custom_data"
    assert stored_data["number"] == 456

    # Assert non-pydantic fields are NOT stored in Redis (should not be present)
    assert "non_pydantic_field" not in stored_data
    assert "another_field" not in stored_data
    assert "temp_data" not in stored_data
