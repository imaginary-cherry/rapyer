import pytest

from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetime
from rapyer.types.integer import RedisInt
from rapyer.types.string import RedisStr
from tests.models.simple_types import DatetimeModel, IntModel, StrModel
from tests.models.unit_types import (
    MultiTypeModel,
    SimpleBoolModel,
    SimpleBytesModel,
    SimpleIntModel,
    SimpleStringModel,
)


@pytest.mark.parametrize("test_value", ["hello", "world", "", "test_string"])
def test_redis_str_model_creation_sanity(test_value):
    # Arrange & Act
    model = SimpleStringModel(name=test_value)

    # Assert
    assert isinstance(model.name, RedisStr)
    assert model.name.key == model.key
    assert model.name.field_path == ".name"
    assert model.name.json_path == "$.name"
    assert str(model.name) == test_value


@pytest.mark.parametrize("test_value", [0, 1, -1, 100, -100])
def test_redis_int_model_creation_sanity(test_value):
    # Arrange & Act
    model = SimpleIntModel(count=test_value)

    # Assert
    assert isinstance(model.count, RedisInt)
    assert model.count.key == model.key
    assert model.count.field_path == ".count"
    assert model.count.json_path == "$.count"
    assert int(model.count) == test_value


@pytest.mark.parametrize("test_value", [True, False])
def test_redis_bool_model_creation_sanity(test_value):
    # Arrange & Act
    model = SimpleBoolModel(flag=test_value)

    # Assert
    assert isinstance(model.flag, bool)
    assert bool(model.flag) == test_value


@pytest.mark.parametrize("test_value", [b"hello", b"world", b"", b"\x00\x01\x02"])
def test_redis_bytes_model_creation_sanity(test_value):
    # Arrange & Act
    model = SimpleBytesModel(data=test_value)

    # Assert
    assert isinstance(model.data, RedisBytes)
    assert model.data.key == model.key
    assert model.data.field_path == ".data"
    assert model.data.json_path == "$.data"
    assert bytes(model.data) == test_value


def test_multi_type_model_creation_sanity():
    # Arrange
    name_val = "test"
    count_val = 42
    flag_val = True
    data_val = b"binary"

    # Act
    model = MultiTypeModel(name=name_val, count=count_val, flag=flag_val, data=data_val)

    # Assert
    assert isinstance(model.name, RedisStr)
    assert isinstance(model.count, RedisInt)
    assert isinstance(model.flag, bool)
    assert isinstance(model.data, RedisBytes)

    assert model.count.key == model.key
    assert model.data.key == model.key

    assert model.count.field_path == ".count"
    assert model.data.field_path == ".data"

    assert model.count.json_path == "$.count"
    assert model.data.json_path == "$.data"


def test_empty_model_creation_sanity():
    # Arrange & Act
    model = MultiTypeModel()

    # Assert
    assert hasattr(model, "name")
    assert hasattr(model, "count")
    assert hasattr(model, "flag")
    assert hasattr(model, "data")


@pytest.mark.asyncio
async def test_redis_int_model_creation_functionality_sanity():
    # Arrange & Act
    model = IntModel(count=42)

    # Assert
    assert isinstance(model.count, RedisInt)
    assert hasattr(model.count, "key")
    assert hasattr(model.count, "field_path")
    assert hasattr(model.count, "redis")
    assert hasattr(model.count, "json_path")
    assert model.count.key == model.key
    assert model.count.field_path == ".count"
    assert model.count.json_path == "$.count"


@pytest.mark.asyncio
async def test_redis_datetime_model_creation_functionality_sanity():
    # Arrange & Act
    model = DatetimeModel()

    # Assert
    assert isinstance(model.created_at, RedisDatetime)
    assert hasattr(model.created_at, "key")
    assert hasattr(model.created_at, "field_path")
    assert hasattr(model.created_at, "redis")
    assert hasattr(model.created_at, "json_path")
    assert model.created_at.key == model.key
    assert model.created_at.field_path == ".created_at"
    assert model.created_at.json_path == "$.created_at"


@pytest.mark.asyncio
async def test_redis_str_model_creation_functionality_sanity():
    # Arrange & Act
    model = StrModel(name="test")

    # Assert
    assert isinstance(model.name, RedisStr)
    assert hasattr(model.name, "key")
    assert hasattr(model.name, "field_path")
    assert hasattr(model.name, "redis")
    assert hasattr(model.name, "json_path")
    assert model.name.key == model.key
    assert model.name.field_path == ".name"
    assert model.name.json_path == "$.name"
