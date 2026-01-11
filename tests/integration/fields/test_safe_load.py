import pytest

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
    with pytest.raises(Exception):
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
async def test_safe_load_list_item_corrupted_returns_none_for_item():
    # Arrange
    model = ModelWithSafeLoadListOfAny(items=["string", 42, True])
    await model.asave()

    # Corrupt the first list item in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.items[0]", "corrupted_base64_data")

    # Act
    loaded = await ModelWithSafeLoadListOfAny.aget(model.key)

    # Assert
    assert loaded.items[0] is None
    assert loaded.items[1] == 42
    assert loaded.items[2] is True


@pytest.mark.asyncio
async def test_safe_load_dict_value_corrupted_returns_none_for_key():
    # Arrange
    model = ModelWithSafeLoadDictOfAny(data={"key1": "value1", "key2": 42, "key3": True})
    await model.asave()

    # Corrupt one dict value in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.data.key1", "corrupted_base64_data")

    # Act
    loaded = await ModelWithSafeLoadDictOfAny.aget(model.key)

    # Assert
    assert loaded.data["key1"] is None
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

    # Act & Assert - aload() doesn't set FAILED_FIELDS_KEY context, so raises
    with pytest.raises(Exception):
        await model.items.aload()


@pytest.mark.asyncio
async def test_unsafe_dict_value_corrupted_raises_error():
    # Arrange
    model = ModelWithUnsafeDictOfAny(data={"key1": "value1", "key2": 42})
    await model.asave()

    # Corrupt one dict value in Redis
    redis = model.Meta.redis
    await redis.json().set(model.key, "$.data.key1", "corrupted_base64_data")

    # Act & Assert - aload() doesn't set FAILED_FIELDS_KEY context, so raises
    with pytest.raises(Exception):
        await model.data.aload()
