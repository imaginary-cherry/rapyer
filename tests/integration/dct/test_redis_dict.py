from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import NoScriptError

from rapyer.base import AtomicRedisModel
from rapyer.errors import PersistentNoScriptError
from rapyer.types.dct import RedisDict
from tests.models.collection_types import (
    IntDictModel,
    StrDictModel,
    BytesDictModel,
    DatetimeDictModel,
    EnumDictModel,
    AnyDictModel,
    BaseModelDictModel,
    BoolDictModel,
    ListDictModel,
    NestedDictModel,
    BaseDictMetadataModel,
    ComprehensiveTestModel,
)
from tests.models.common import Status, Person


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data", "new_item_key", "new_item_value"],
    [
        [StrDictModel, {"key1": "value1"}, "key2", "value2"],
        [IntDictModel, {"key1": 42}, "key2", 100],
        [BytesDictModel, {"key1": b"data1"}, "key2", b"data2"],
        [
            DatetimeDictModel,
            {"key1": datetime(2023, 1, 1)},
            "key2",
            datetime(2023, 2, 1),
        ],
        [EnumDictModel, {"key1": Status.ACTIVE}, "key2", Status.PENDING],
        [AnyDictModel, {"key1": "mixed"}, "key2", 42],
        [
            BaseModelDictModel,
            {"key1": Person(name="Alice", age=30, email="alice@example.com")},
            "key2",
            Person(name="Bob", age=25, email="bob@example.com"),
        ],
        [BoolDictModel, {"key1": True}, "key2", False],
        [ListDictModel, {"key1": ["item1", "item2"]}, "key2", ["item3", "item4"]],
        [
            NestedDictModel,
            {"key1": {"nested1": "value1"}},
            "key2",
            {"nested2": "value2"},
        ],
        [BaseDictMetadataModel, {"key1": "value1"}, "key2", "value2"],
    ],
)
async def test_redis_dict__setitem__check_local_consistency_sanity(
    model_class: type[BaseDictMetadataModel], initial_data, new_item_key, new_item_value
):
    # Arrange
    user = model_class(metadata=initial_data)
    await user.asave()

    # Act
    await user.metadata.aset_item(new_item_key, new_item_value)
    await user.asave()  # Sync with Redis

    # Assert
    fresh_user = model_class()
    fresh_user.pk = user.pk
    fresh_user.metadata = await fresh_user.metadata.aload()
    assert user.metadata == fresh_user.metadata


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data", "key_to_delete"],
    [
        [StrDictModel, {"key1": "value1", "key2": "value2"}, "key1"],
        [IntDictModel, {"key1": 42, "key2": 100}, "key1"],
        [BytesDictModel, {"key1": b"data1", "key2": b"data2"}, "key1"],
        [
            DatetimeDictModel,
            {"key1": datetime(2023, 1, 1), "key2": datetime(2023, 2, 1)},
            "key1",
        ],
        [EnumDictModel, {"key1": Status.ACTIVE, "key2": Status.PENDING}, "key1"],
        [AnyDictModel, {"key1": "mixed", "key2": 42}, "key1"],
        [BaseDictMetadataModel, {"key1": "value1", "key2": "value2"}, "key1"],
    ],
)
async def test_redis_dict__delitem__check_local_consistency_sanity(
    model_class: type[BaseDictMetadataModel], initial_data, key_to_delete
):
    # Arrange
    user = model_class(metadata=initial_data)
    await user.asave()

    # Act
    await user.metadata.adel_item(key_to_delete)
    await user.asave()  # Sync with Redis

    # Assert
    fresh_user = model_class()
    fresh_user.pk = user.pk
    fresh_user.metadata = await fresh_user.metadata.aload()
    assert user.metadata == fresh_user.metadata


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data", "update_data"],
    [
        [StrDictModel, {"key1": "value1"}, {"key2": "value2", "key3": "value3"}],
        [IntDictModel, {"key1": 42}, {"key2": 100, "key3": 200}],
        [BytesDictModel, {"key1": b"data1"}, {"key2": b"data2", "key3": b"data3"}],
        [
            DatetimeDictModel,
            {"key1": datetime(2023, 1, 1)},
            {"key2": datetime(2023, 2, 1), "key3": datetime(2023, 3, 1)},
        ],
        [
            EnumDictModel,
            {"key1": Status.ACTIVE},
            {"key2": Status.PENDING, "key3": Status.INACTIVE},
        ],
        [AnyDictModel, {"key1": "mixed"}, {"key2": 42, "key3": [1, 2, 3]}],
        [
            BaseDictMetadataModel,
            {"key1": "value1"},
            {"key2": "value2", "key3": "value3"},
        ],
    ],
)
async def test_redis_dict__update__check_local_consistency_sanity(
    model_class: type[BaseDictMetadataModel], initial_data, update_data
):
    # Arrange
    user = model_class(metadata=initial_data)
    await user.asave()

    # Act
    await user.metadata.aupdate(**update_data)
    await user.asave()  # Sync with Redis

    # Assert
    fresh_user = model_class()
    fresh_user.pk = user.pk
    fresh_user.metadata = await fresh_user.metadata.aload()
    assert user.metadata == fresh_user.metadata


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data"],
    [
        [StrDictModel, {"key1": "value1", "key2": "value2"}],
        [IntDictModel, {"key1": 42, "key2": 100}],
        [BytesDictModel, {"key1": b"data1", "key2": b"data2"}],
        [
            DatetimeDictModel,
            {"key1": datetime(2023, 1, 1), "key2": datetime(2023, 2, 1)},
        ],
        [EnumDictModel, {"key1": Status.ACTIVE, "key2": Status.PENDING}],
        [AnyDictModel, {"key1": "mixed", "key2": 42}],
        [BaseDictMetadataModel, {"key1": "value1", "key2": "value2"}],
    ],
)
async def test_redis_dict__clear__check_local_consistency_sanity(
    model_class: type[BaseDictMetadataModel], initial_data
):
    # Arrange
    user = model_class(metadata=initial_data)
    await user.asave()

    # Act
    await user.metadata.aclear()
    await user.asave()  # Sync with Redis

    # Assert
    fresh_user = model_class()
    fresh_user.pk = user.pk
    fresh_user.metadata = await fresh_user.metadata.aload()
    assert len(user.metadata) == 0
    assert user.metadata == fresh_user.metadata


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data", "new_item_key", "new_item_value"],
    [
        [StrDictModel, {"key1": "value1"}, "key2", "value2"],
        [IntDictModel, {"key1": 42}, "key2", 100],
        [BytesDictModel, {"key1": b"data1"}, "key2", b"data2"],
        [
            DatetimeDictModel,
            {"key1": datetime(2023, 1, 1)},
            "key2",
            datetime(2023, 2, 1),
        ],
        [EnumDictModel, {"key1": Status.ACTIVE}, "key2", Status.PENDING],
        [AnyDictModel, {"key1": "mixed"}, "key2", 42],
        [BaseDictMetadataModel, {"key1": "value1"}, "key2", "value2"],
    ],
)
async def test_redis_dict__load__check_redis_load_sanity(
    model_class: type[BaseDictMetadataModel], initial_data, new_item_key, new_item_value
):
    # Arrange
    user = model_class(metadata=initial_data)
    await user.asave()
    # Use another user instance to set a value and verify load works
    other_user = model_class()
    other_user.pk = user.pk
    other_user.metadata = await other_user.metadata.aload()
    await other_user.metadata.aset_item(new_item_key, new_item_value)

    # Act
    user.metadata = await user.metadata.aload()

    # Assert
    fresh_user = model_class()
    fresh_user.pk = user.pk
    fresh_user.metadata = await fresh_user.metadata.aload()
    assert user.metadata == fresh_user.metadata
    assert new_item_key in user.metadata
    assert user.metadata[new_item_key] == new_item_value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data", "key_to_pop", "expected_value"],
    [
        [StrDictModel, {"key1": "value1", "key2": "value2"}, "key1", "value1"],
        [IntDictModel, {"key1": 42, "key2": 100}, "key1", 42],
        [BytesDictModel, {"key1": b"data1", "key2": b"data2"}, "key1", b"data1"],
        [
            DatetimeDictModel,
            {"key1": datetime(2023, 1, 1), "key2": datetime(2023, 2, 1)},
            "key1",
            datetime(2023, 1, 1),
        ],
        [
            EnumDictModel,
            {"key1": Status.ACTIVE, "key2": Status.PENDING},
            "key1",
            Status.ACTIVE,
        ],
        [AnyDictModel, {"key1": "mixed", "key2": 42}, "key1", "mixed"],
        [BaseDictMetadataModel, {"key1": "value1", "key2": "value2"}, "key1", "value1"],
    ],
)
async def test_redis_dict__pop__check_redis_pop_sanity(
    model_class: type[BaseDictMetadataModel], initial_data, key_to_pop, expected_value
):
    # Arrange
    user = model_class(metadata=initial_data)
    await user.asave()

    # Act
    popped_value = await user.metadata.apop(key_to_pop)

    # Assert
    fresh_user = model_class()
    fresh_user.pk = user.pk
    fresh_user.metadata = await fresh_user.metadata.aload()
    assert user.metadata == fresh_user.metadata
    assert popped_value == expected_value
    assert key_to_pop not in user.metadata
    assert len(user.metadata) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data", "default_value"],
    [
        [StrDictModel, {"key1": "value1"}, "default_value"],
        [IntDictModel, {"key1": 42}, 999],
        [BytesDictModel, {"key1": b"data1"}, b"default"],
        [DatetimeDictModel, {"key1": datetime(2023, 1, 1)}, datetime(2023, 12, 31)],
        [EnumDictModel, {"key1": Status.ACTIVE}, Status.INACTIVE],
        [AnyDictModel, {"key1": "mixed"}, "default_any"],
        [BaseDictMetadataModel, {"key1": "value1"}, "default_value"],
    ],
)
async def test_redis_dict__pop_with_default__check_default_return_sanity(
    model_class: type[BaseDictMetadataModel], initial_data, default_value
):
    # Arrange
    user = model_class(metadata=initial_data)
    await user.asave()

    # Act
    result = await user.metadata.apop("nonexistent", default_value)

    # Assert
    assert result == default_value
    assert len(user.metadata) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data"],
    [
        [StrDictModel, {"key1": "value1", "key2": "value2"}],
        [IntDictModel, {"key1": 42, "key2": 100}],
        [BytesDictModel, {"key1": b"data1", "key2": b"data2"}],
        [
            DatetimeDictModel,
            {"key1": datetime(2023, 1, 1), "key2": datetime(2023, 2, 1)},
        ],
        [EnumDictModel, {"key1": Status.ACTIVE, "key2": Status.PENDING}],
        [AnyDictModel, {"key1": "mixed", "key2": 42}],
        [BaseDictMetadataModel, {"key1": "value1", "key2": "value2"}],
    ],
)
async def test_redis_dict__popitem__check_redis_popitem_sanity(
    model_class: type[BaseDictMetadataModel], initial_data
):
    # Arrange
    user = model_class(metadata=initial_data)
    await user.asave()

    # Act
    popped_value = await user.metadata.apopitem()

    # Assert
    fresh_user = model_class()
    fresh_user.pk = user.pk
    fresh_user.metadata = await fresh_user.metadata.aload()
    assert user.metadata == fresh_user.metadata
    # popitem should remove one item, leaving one remaining
    assert len(user.metadata) == 1
    # Verify that one of the original values was removed by checking remaining values
    remaining_values = set(user.metadata.values())
    original_values = set(initial_data.values())
    removed_values = original_values - remaining_values
    assert len(removed_values) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data"],
    [
        [StrDictModel, {"key1": "value1"}],
        [IntDictModel, {"key1": 42}],
        [BytesDictModel, {"key1": b"data1"}],
        [DatetimeDictModel, {"key1": datetime(2023, 1, 1)}],
        [EnumDictModel, {"key1": Status.ACTIVE}],
        [AnyDictModel, {"key1": "mixed"}],
        [BaseDictMetadataModel, {"key1": "value1"}],
    ],
)
async def test_redis_dict__update_with_kwargs__check_local_consistency_sanity(
    model_class: type[AtomicRedisModel], initial_data
):
    # Arrange
    user = model_class(metadata=initial_data)
    await user.asave()

    # Act
    if model_class == StrDictModel:
        await user.metadata.aupdate(key2="value2", key3="value3")
    elif model_class == IntDictModel:
        await user.metadata.aupdate(key2=100, key3=200)
    elif model_class == BytesDictModel:
        await user.metadata.aupdate(key2=b"data2", key3=b"data3")
    elif model_class == DatetimeDictModel:
        await user.metadata.aupdate(
            key2=datetime(2023, 2, 1), key3=datetime(2023, 3, 1)
        )
    elif model_class == EnumDictModel:
        await user.metadata.aupdate(key2=Status.PENDING, key3=Status.INACTIVE)
    elif model_class == AnyDictModel:
        await user.metadata.aupdate(key2=42, key3=[1, 2, 3])
    elif model_class == BaseDictMetadataModel:
        await user.metadata.aupdate(key2="value2", key3="value3")
    await user.asave()  # Sync with Redis

    # Assert
    fresh_user = model_class()
    fresh_user.pk = user.pk
    fresh_user.metadata = await fresh_user.metadata.aload()
    assert user.metadata == fresh_user.metadata
    assert len(user.metadata) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data"],
    [
        [StrDictModel, {"key1": "value1", "key2": "value2"}],
        [IntDictModel, {"key1": 42, "key2": 100}],
        [BytesDictModel, {"key1": b"data1", "key2": b"data2"}],
        [
            DatetimeDictModel,
            {"key1": datetime(2023, 1, 1), "key2": datetime(2023, 2, 1)},
        ],
        [EnumDictModel, {"key1": Status.ACTIVE, "key2": Status.PENDING}],
        [AnyDictModel, {"key1": "mixed", "key2": 42}],
        [BaseDictMetadataModel, {"key1": "value1", "key2": "value2"}],
    ],
)
async def test_redis_dict__clone__check_clone_functionality_sanity(
    model_class: type[BaseDictMetadataModel], initial_data
):
    # Arrange
    user = model_class(metadata=initial_data)

    # Act
    cloned_dict = user.metadata.clone()

    # Assert
    assert isinstance(cloned_dict, dict)
    # Should be regular dict, not RedisDict
    assert not isinstance(cloned_dict, type(user.metadata))
    assert cloned_dict == initial_data
    assert cloned_dict == user.metadata
    # Verify it's a copy, not the same object
    if model_class == StrDictModel:
        cloned_dict["key3"] = "value3"
    elif model_class == IntDictModel:
        cloned_dict["key3"] = 200
    elif model_class == BytesDictModel:
        cloned_dict["key3"] = b"data3"
    elif model_class == DatetimeDictModel:
        cloned_dict["key3"] = datetime(2023, 3, 1)
    elif model_class == EnumDictModel:
        cloned_dict["key3"] = Status.INACTIVE
    elif model_class == AnyDictModel:
        cloned_dict["key3"] = [1, 2, 3]
    elif model_class == BaseDictMetadataModel:
        cloned_dict["key3"] = "value3"
    assert "key3" not in user.metadata


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_class",
    [
        StrDictModel,
        IntDictModel,
        BytesDictModel,
        DatetimeDictModel,
        EnumDictModel,
        AnyDictModel,
        BaseDictMetadataModel,
    ],
)
async def test_redis_dict__popitem_empty_dict__check_key_error_sanity(
    model_class: type[BaseDictMetadataModel],
):
    # Arrange
    user = model_class(metadata={})
    await user.asave()

    # Act & Assert
    with pytest.raises(KeyError, match="popitem\\(\\): dictionary is empty"):
        await user.metadata.apopitem()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data", "additional_data"],
    [
        [StrDictModel, {"key1": "value1"}, {"key2": "value2"}],
        [IntDictModel, {"key1": 42}, {"key2": 100}],
        [BytesDictModel, {"key1": b"data1"}, {"key2": b"data2"}],
        [
            DatetimeDictModel,
            {"key1": datetime(2023, 1, 1)},
            {"key2": datetime(2023, 2, 1)},
        ],
        [EnumDictModel, {"key1": Status.ACTIVE}, {"key2": Status.PENDING}],
        [AnyDictModel, {"key1": "mixed"}, {"key2": 42}],
        [BaseDictMetadataModel, {"key1": "value1"}, {"key2": "value2"}],
    ],
)
async def test__redis_dict_model__ior_sanity(
    model_class: type[BaseDictMetadataModel], initial_data, additional_data
):
    # Arrange
    user = model_class(metadata=initial_data)

    # Act
    user.metadata |= additional_data

    # Assert
    expected_result = {**initial_data, **additional_data}
    assert user.metadata == expected_result
    assert isinstance(user.metadata, RedisDict)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "default_value"],
    [
        [StrDictModel, "default_value"],
        [IntDictModel, 999],
        [BytesDictModel, b"default"],
        [DatetimeDictModel, datetime(2023, 12, 31)],
        [EnumDictModel, Status.INACTIVE],
        [AnyDictModel, "default_any"],
        [BaseDictMetadataModel, "default_value"],
    ],
)
async def test_redis_dict__apop_empty_redis__check_default_returned_sanity(
    model_class: type[BaseDictMetadataModel], default_value
):
    # Arrange
    user = model_class()
    await user.asave()

    # Act
    result = await user.metadata.apop("nonexistent_key", default_value)

    # Assert
    assert result == default_value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_class",
    [
        StrDictModel,
        IntDictModel,
        BytesDictModel,
        DatetimeDictModel,
        EnumDictModel,
        AnyDictModel,
        BaseDictMetadataModel,
    ],
)
async def test_redis_dict__apop_empty_redis__check_no_default_sanity(
    model_class: type[BaseDictMetadataModel],
):
    # Arrange
    user = model_class()
    await user.asave()

    # Act
    result = await user.metadata.apop("nonexistent_key", default=None)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_redis_dict__apop_raises_persistent_noscript_error_when_scripts_keep_failing(
    disable_registry_noscript_recovery,
):
    # Arrange
    model = ComprehensiveTestModel(metadata={"key1": "value1"})
    await model.asave()

    mock_evalsha = AsyncMock(side_effect=NoScriptError("NOSCRIPT"))

    # Act & Assert
    with patch.object(model.Meta.redis, "evalsha", mock_evalsha):
        with pytest.raises(PersistentNoScriptError) as exc_info:
            await model.metadata.apop("key1")

        assert "server-side" in str(exc_info.value).lower()
