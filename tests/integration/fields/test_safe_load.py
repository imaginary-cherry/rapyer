import pytest

from rapyer.errors.base import CantSerializeRedisValueError
from tests.models.complex_types import (
    OuterModelWithRedisNested,
    ContainerModel,
    InnerRedisModel,
)
from tests.models.safe_load_types import (
    ModelWithSafeLoadField,
    ModelWithMultipleSafeLoadFields,
    ModelWithMixedFields,
    ModelWithSafeLoadAllConfig,
    ModelWithSafeLoadListOfAny,
    ModelWithSafeLoadDictOfAny,
    ModelWithUnsafeListOfAny,
    ModelWithUnsafeDictOfAny,
)


@pytest.mark.asyncio
async def test_safe_load_field_success_normal_load_sanity():
    # Arrange
    model = ModelWithSafeLoadField(safe_type_field=str, normal_field="test")

    # Act
    await model.asave()
    loaded = await ModelWithSafeLoadField.aget(model.key)

    # Assert
    assert loaded.safe_type_field is str
    assert loaded.normal_field == "test"
    assert len(loaded.failed_fields) == 0


@pytest.mark.asyncio
async def test_safe_load_field_corrupted_returns_none_and_tracks_failure():
    # Arrange
    model = ModelWithSafeLoadField(safe_type_field=str, normal_field="test")
    await model.asave()

    # Corrupt the pickled data in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.safe_type_field", "corrupted_base64_data")

    # Act
    loaded = await ModelWithSafeLoadField.aget(model.key)

    # Assert
    assert loaded.safe_type_field is None
    assert loaded.normal_field == "test"
    assert "safe_type_field" in loaded.failed_fields


@pytest.mark.asyncio
async def test_safe_load_multiple_fields_tracks_all_failures():
    # Arrange
    model = ModelWithMultipleSafeLoadFields(
        safe_field_1=str, safe_field_2=int, normal_field="test"
    )
    await model.asave()

    # Corrupt both safe fields
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.safe_field_1", "corrupted1")
    await redis.json().set(model.key, "$.safe_field_2", "corrupted2")

    # Act
    loaded = await ModelWithMultipleSafeLoadFields.aget(model.key)

    # Assert
    assert loaded.safe_field_1 is None
    assert loaded.safe_field_2 is None
    assert loaded.normal_field == "test"
    assert "safe_field_1" in loaded.failed_fields
    assert "safe_field_2" in loaded.failed_fields


@pytest.mark.asyncio
async def test_unsafe_field_corrupted_raises_error():
    # Arrange
    model = ModelWithMixedFields(safe_field=str, unsafe_field=int, normal_field="test")
    await model.asave()

    # Corrupt the unsafe field
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.unsafe_field", "corrupted")

    # Act & Assert
    with pytest.raises(CantSerializeRedisValueError):
        await ModelWithMixedFields.aget(model.key)


@pytest.mark.asyncio
async def test_failed_fields_empty_on_new_model_sanity():
    # Arrange & Act
    model = ModelWithSafeLoadField(safe_type_field=str, normal_field="test")

    # Assert
    assert len(model.failed_fields) == 0


@pytest.mark.asyncio
async def test_safe_load_all_config_success_normal_load_sanity():
    # Arrange
    model = ModelWithSafeLoadAllConfig(
        type_field_1=str, type_field_2=int, normal_field="test"
    )

    # Act
    await model.asave()
    loaded = await ModelWithSafeLoadAllConfig.aget(model.key)

    # Assert
    assert loaded.type_field_1 is str
    assert loaded.type_field_2 is int
    assert loaded.normal_field == "test"
    assert len(loaded.failed_fields) == 0


@pytest.mark.asyncio
async def test_safe_load_all_config_corrupted_returns_none_and_tracks_failure():
    # Arrange
    model = ModelWithSafeLoadAllConfig(
        type_field_1=str, type_field_2=int, normal_field="test"
    )
    await model.asave()

    # Corrupt the pickled data in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.type_field_1", "corrupted_data")

    # Act
    loaded = await ModelWithSafeLoadAllConfig.aget(model.key)

    # Assert
    assert loaded.type_field_1 is None
    assert loaded.type_field_2 is int
    assert loaded.normal_field == "test"
    assert "type_field_1" in loaded.failed_fields


@pytest.mark.asyncio
async def test_safe_load_all_config_multiple_corrupted_tracks_all_failures():
    # Arrange
    model = ModelWithSafeLoadAllConfig(
        type_field_1=str, type_field_2=int, normal_field="test"
    )
    await model.asave()

    # Corrupt both fields
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.type_field_1", "corrupted1")
    await redis.json().set(model.key, "$.type_field_2", "corrupted2")

    # Act
    loaded = await ModelWithSafeLoadAllConfig.aget(model.key)

    # Assert
    assert loaded.type_field_1 is None
    assert loaded.type_field_2 is None
    assert loaded.normal_field == "test"
    assert "type_field_1" in loaded.failed_fields
    assert "type_field_2" in loaded.failed_fields


@pytest.mark.asyncio
async def test_safe_load_list_item_corrupted_skips_item():
    # Arrange
    model = ModelWithSafeLoadListOfAny(items=["string", 42, True])
    await model.asave()

    # Corrupt the first list item in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.items[0]", "corrupted_base64_data")

    # Act
    loaded = await ModelWithSafeLoadListOfAny.aget(model.key)

    # Assert
    assert len(loaded.items) == 2
    assert loaded.items[0] == 42
    assert loaded.items[1] is True


@pytest.mark.asyncio
async def test_safe_load_dict_value_corrupted_skips_key():
    # Arrange
    model = ModelWithSafeLoadDictOfAny(
        data={"key1": "value1", "key2": 42, "key3": True}
    )
    await model.asave()

    # Corrupt one dict value in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.data.key1", "corrupted_base64_data")

    # Act
    loaded = await ModelWithSafeLoadDictOfAny.aget(model.key)

    # Assert
    assert "key1" not in loaded.data
    assert len(loaded.data) == 2
    assert loaded.data["key2"] == 42
    assert loaded.data["key3"] is True


@pytest.mark.asyncio
async def test_unsafe_list_item_corrupted_raises_error():
    # Arrange
    model = ModelWithUnsafeListOfAny(items=["string", 42, True])
    await model.asave()

    # Corrupt the first list item in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.items[0]", "corrupted_base64_data")

    # Act & Assert
    with pytest.raises(CantSerializeRedisValueError):
        await ModelWithUnsafeListOfAny.aget(model.key)


@pytest.mark.asyncio
async def test_unsafe_dict_value_corrupted_raises_error():
    # Arrange
    model = ModelWithUnsafeDictOfAny(data={"key1": "value1", "key2": 42})
    await model.asave()

    # Corrupt one dict value in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.data.key1", "corrupted_base64_data")

    # Act & Assert
    with pytest.raises(CantSerializeRedisValueError):
        await ModelWithUnsafeDictOfAny.aget(model.key)


@pytest.mark.asyncio
async def test_nested_safe_list_item_corrupted_skips_item():
    # Arrange
    inner = InnerRedisModel(tags=["tag1"], counter=5, safe_data=["item1", 42, True])
    container = ContainerModel(inner_redis=inner, description="test")
    model = OuterModelWithRedisNested(container=container, outer_data=[1, 2, 3])
    await model.asave()

    # Corrupt the first item in the nested safe list
    redis = model.Meta.redis
    await redis.json().set(
        model.key, "$.container.inner_redis.safe_data[0]", "corrupted_data"
    )

    # Act
    loaded = await OuterModelWithRedisNested.aget(model.key)

    # Assert
    assert loaded.container.description == "test"
    assert loaded.container.inner_redis.counter == 5
    assert len(loaded.container.inner_redis.safe_data) == 2
    assert loaded.container.inner_redis.safe_data[0] == 42
    assert loaded.container.inner_redis.safe_data[1] is True


@pytest.mark.asyncio
async def test_aload_with_corrupted_safe_field_succeeds():
    # Arrange
    model = ModelWithSafeLoadField(safe_type_field=str, normal_field="test")
    await model.asave()

    # Corrupt the safe field in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.safe_type_field", "corrupted_base64_data")

    # Act
    loaded = await model.aload()

    # Assert
    assert loaded.safe_type_field is None
    assert loaded.normal_field == "test"
    assert "safe_type_field" in loaded.failed_fields


@pytest.mark.asyncio
async def test_aload_with_corrupted_unsafe_field_raises_error():
    # Arrange
    model = ModelWithMixedFields(safe_field=str, unsafe_field=int, normal_field="test")
    await model.asave()

    # Corrupt the unsafe field in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.unsafe_field", "corrupted")

    # Act & Assert
    with pytest.raises(CantSerializeRedisValueError):
        await model.aload()


@pytest.mark.asyncio
async def test_aload_with_multiple_corrupted_safe_fields_succeeds():
    # Arrange
    model = ModelWithMultipleSafeLoadFields(
        safe_field_1=str, safe_field_2=int, normal_field="test"
    )
    await model.asave()

    # Corrupt both safe fields in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.safe_field_1", "corrupted1")
    await redis.json().set(model.key, "$.safe_field_2", "corrupted2")

    # Act
    loaded = await model.aload()

    # Assert
    assert loaded.safe_field_1 is None
    assert loaded.safe_field_2 is None
    assert loaded.normal_field == "test"
    assert "safe_field_1" in loaded.failed_fields
    assert "safe_field_2" in loaded.failed_fields


@pytest.mark.asyncio
async def test_aload_with_corrupted_safe_list_item_skips_item():
    # Arrange
    model = ModelWithSafeLoadListOfAny(items=["string", 42, True])
    await model.asave()

    # Corrupt the first list item in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.items[0]", "corrupted_base64_data")

    # Act
    loaded = await model.aload()

    # Assert
    assert len(loaded.items) == 2
    assert loaded.items[0] == 42
    assert loaded.items[1] is True


@pytest.mark.asyncio
async def test_aload_with_corrupted_unsafe_list_item_raises_error():
    # Arrange
    model = ModelWithUnsafeListOfAny(items=["string", 42, True])
    await model.asave()

    # Corrupt the first list item in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.items[0]", "corrupted_base64_data")

    # Act & Assert
    with pytest.raises(CantSerializeRedisValueError):
        await model.aload()


@pytest.mark.asyncio
async def test_aload_with_corrupted_safe_dict_value_skips_key():
    # Arrange
    model = ModelWithSafeLoadDictOfAny(
        data={"key1": "value1", "key2": 42, "key3": True}
    )
    await model.asave()

    # Corrupt one dict value in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.data.key1", "corrupted_base64_data")

    # Act
    loaded = await model.aload()

    # Assert
    assert "key1" not in loaded.data
    assert len(loaded.data) == 2
    assert loaded.data["key2"] == 42
    assert loaded.data["key3"] is True


@pytest.mark.asyncio
async def test_aload_with_corrupted_unsafe_dict_value_raises_error():
    # Arrange
    model = ModelWithUnsafeDictOfAny(data={"key1": "value1", "key2": 42})
    await model.asave()

    # Corrupt one dict value in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.data.key1", "corrupted_base64_data")

    # Act & Assert
    with pytest.raises(CantSerializeRedisValueError):
        await model.aload()


@pytest.mark.asyncio
async def test_afind_with_corrupted_safe_field_succeeds():
    # Arrange
    model1 = ModelWithMultipleSafeLoadFields(
        safe_field_1=str, safe_field_2=int, normal_field="test1"
    )
    model2 = ModelWithMultipleSafeLoadFields(
        safe_field_1=float, safe_field_2=list, normal_field="test2"
    )
    await model1.asave()
    await model2.asave()

    # Corrupt the safe field in one model
    redis = model1.Meta.redis
    await redis.json().set(model1.key, "$.safe_field_1", "corrupted_base64_data")

    # Act
    loaded_models = await ModelWithMultipleSafeLoadFields.afind()

    # Assert
    assert len(loaded_models) == 2
    loaded_by_key = {m.key: m for m in loaded_models}

    corrupted_model = loaded_by_key[model1.key]
    assert corrupted_model.safe_field_1 is None
    assert corrupted_model.safe_field_2 is int
    assert corrupted_model.normal_field == "test1"
    assert "safe_field_1" in corrupted_model.failed_fields

    valid_model = loaded_by_key[model2.key]
    assert valid_model.safe_field_1 is float
    assert valid_model.safe_field_2 is list
    assert valid_model.normal_field == "test2"
    assert len(valid_model.failed_fields) == 0


@pytest.mark.asyncio
async def test_afind_with_corrupted_unsafe_field_raises_error():
    # Arrange
    model = ModelWithMixedFields(safe_field=str, unsafe_field=int, normal_field="test")
    await model.asave()

    # Corrupt the unsafe field in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.unsafe_field", "corrupted")

    # Act & Assert
    with pytest.raises(CantSerializeRedisValueError):
        await ModelWithMixedFields.afind()
