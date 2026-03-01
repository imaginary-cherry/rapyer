from datetime import datetime

import pytest

from rapyer.base import AtomicRedisModel
from rapyer.types.base import RedisType
from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetime
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.string import RedisStr
from tests.models.collection_types import (
    IntDictModel,
    StrDictModel,
    BytesDictModel,
    DatetimeDictModel,
    EnumDictModel,
    AnyDictModel,
    Status,
    BaseDictMetadataModel,
    SimpleListModel,
    SimpleIntListModel,
    SimpleDictModel,
)
from tests.models.complex_types import OuterModel
from tests.models.simple_types import (
    StrModel,
    IntModel,
    BoolModel,
    BytesModel,
    DatetimeModel,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "field_name", "expected_redis_type", "expected_json_path"],
    [
        [StrModel, "name", RedisStr, "$.name"],
        [StrModel, "description", RedisStr, "$.description"],
        [IntModel, "count", RedisInt, "$.count"],
        [IntModel, "score", RedisInt, "$.score"],
        [BytesModel, "data", RedisBytes, "$.data"],
        [BytesModel, "binary_content", RedisBytes, "$.binary_content"],
        [SimpleListModel, "items", RedisList, "$.items"],
        [SimpleIntListModel, "numbers", RedisList, "$.numbers"],
        [SimpleDictModel, "data", RedisDict, "$.data"],
        [StrDictModel, "metadata", RedisDict, "$.metadata"],
    ],
)
async def test_model_creation_with_defaults__check_redis_type_inheritance_and_json_path_sanity(
    model_class: type[AtomicRedisModel],
    field_name: str,
    expected_redis_type: type,
    expected_json_path: str,
):
    # Arrange & Act
    model = model_class()

    # Assert
    field_value = getattr(model, field_name)
    assert isinstance(field_value, expected_redis_type)
    assert isinstance(field_value, RedisType) or isinstance(
        field_value, AtomicRedisModel
    )
    assert field_value.json_path == expected_json_path


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "field_name", "expected_default_value"],
    [
        [StrModel, "name", ""],
        [StrModel, "description", "default"],
        [IntModel, "count", 0],
        [IntModel, "score", 100],
        [BoolModel, "is_active", False],
        [BoolModel, "is_deleted", True],
        [BytesModel, "data", b""],
        [BytesModel, "binary_content", b"default"],
        [SimpleListModel, "items", []],
        [SimpleIntListModel, "numbers", []],
        [SimpleDictModel, "data", {}],
        [StrDictModel, "metadata", {}],
    ],
)
async def test_model_creation_with_defaults__check_default_values_sanity(
    model_class: type[AtomicRedisModel], field_name: str, expected_default_value
):
    # Arrange & Act
    model = model_class()

    # Assert
    field_value = getattr(model, field_name)
    assert field_value == expected_default_value


@pytest.mark.asyncio
async def test_model_creation_with_nested_base_model__check_atomic_base_inheritance_and_json_path_sanity():
    # Arrange & Act
    model = OuterModel()

    # Assert
    assert isinstance(model.middle_model, AtomicRedisModel)
    assert model.middle_model.json_path == "$.middle_model"


@pytest.mark.asyncio
async def test_model_creation_with_datetime_field__check_datetime_default_factory_sanity():
    # Arrange & Act
    model = DatetimeModel()

    # Assert
    assert isinstance(model.created_at, RedisDatetime)
    assert isinstance(model.created_at, datetime)
    assert model.created_at.json_path == "$.created_at"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class", "initial_data"],
    [
        [StrDictModel, {"key1": "value1"}],
        [IntDictModel, {"key1": 42}],
        [DatetimeDictModel, {"key1": datetime(2023, 1, 1)}],
        [BytesDictModel, {"key1": b"data1"}],
        [EnumDictModel, {"key1": Status.ACTIVE}],
        [AnyDictModel, {"key1": "mixed"}],
    ],
)
async def test_redis_dict__model_creation__check_redis_dict_instance_sanity(
    model_class: type[BaseDictMetadataModel], initial_data
):
    # Arrange & Act
    user = model_class(metadata=initial_data)

    # Assert
    assert isinstance(user.metadata, RedisDict)
    assert hasattr(user.metadata, "key")
    assert hasattr(user.metadata, "field_path")
    assert hasattr(user.metadata, "redis")
    assert hasattr(user.metadata, "json_path")
    assert user.metadata.key == user.key
    assert user.metadata.field_path == ".metadata"
    assert user.metadata.json_path == "$.metadata"


@pytest.mark.asyncio
async def test_model_creation__check_private_and_class_fields_not_converted_to_redis_types_sanity():
    # Arrange
    from typing import ClassVar
    from pydantic import PrivateAttr

    class TestModel(AtomicRedisModel):
        _private_field: str = PrivateAttr(default="private")
        class_field: ClassVar[int] = 42

    # Act
    model = TestModel()

    # Assert
    assert model.__annotations__["_private_field"] == str
    assert model.__annotations__["class_field"] == ClassVar[int]

    assert hasattr(model, "_private_field")
    assert not isinstance(model._private_field, RedisType)
    assert model._private_field == "private"

    assert hasattr(TestModel, "class_field")
    assert not isinstance(TestModel.class_field, RedisType)
    assert TestModel.class_field == 42


@pytest.mark.asyncio
async def test_model_equality__atomic_model_vs_non_base_model__returns_false():
    # Arrange
    class ModelA(AtomicRedisModel):
        name: str = ""

    model_a = ModelA(name="asdf")

    # Act
    result = model_a == "asdf"

    # Assert
    assert result is False
