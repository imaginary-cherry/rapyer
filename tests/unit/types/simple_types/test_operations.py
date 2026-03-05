import pytest

from rapyer.types.byte import RedisBytes
from rapyer.types.integer import RedisInt
from rapyer.types.string import RedisStr
from tests.models.unit_types import (
    SimpleBoolModel,
    SimpleBytesModel,
    SimpleIntModel,
    SimpleStringModel,
)


@pytest.mark.parametrize(
    "initial_value,new_value", [("hello", "world"), ("", "test"), ("old", "new")]
)
def test_redis_str_operations_sanity(initial_value, new_value):
    # Arrange
    model = SimpleStringModel(name=initial_value)
    model.name._base_model_link = model

    # Act - Test assignment
    model.name = new_value

    # Assert
    assert isinstance(model.name, RedisStr)
    assert str(model.name) == new_value
    assert model.name.key == model.key
    assert model.name.field_path == ".name"


@pytest.mark.parametrize(
    "initial_value,increment", [(0, 1), (10, 5), (-5, 3), (100, -10)]
)
def test_redis_int_operations_sanity(initial_value, increment):
    # Arrange
    model = SimpleIntModel(count=initial_value)

    # Act - Test assignment
    new_value = initial_value + increment
    model.count = new_value

    # Assert
    assert isinstance(model.count, RedisInt)
    assert int(model.count) == new_value
    assert model.count.key == model.key
    assert model.count.field_path == ".count"


@pytest.mark.parametrize("initial_value", [True, False])
def test_redis_bool_operations_sanity(initial_value):
    # Arrange
    model = SimpleBoolModel(flag=initial_value)

    # Act - Test assignment
    new_value = not initial_value
    model.flag = new_value

    # Assert
    assert isinstance(model.flag, bool)
    assert bool(model.flag) == new_value


@pytest.mark.parametrize(
    "initial_value,new_value",
    [(b"hello", b"world"), (b"", b"test"), (b"\x00\x01", b"\x02\x03")],
)
def test_redis_bytes_operations_sanity(initial_value, new_value):
    # Arrange
    model = SimpleBytesModel(data=initial_value)

    # Act - Test assignment
    model.data = new_value

    # Assert
    assert isinstance(model.data, RedisBytes)
    assert bytes(model.data) == new_value
    assert model.data.key == model.key
    assert model.data.field_path == ".data"


def test_redis_str_concatenation_operation_sanity():
    # Arrange
    model = SimpleStringModel(name="hello")

    # Act
    result = model.name + " world"

    # Assert
    assert result == "hello world"
    assert isinstance(model.name, RedisStr)
    assert model.name.key == model.key
    assert model.name.field_path == ".name"


@pytest.mark.parametrize(
    ["initial_value", "other_value"],
    [["hello", " world"], ["", "test"], ["old", " new"]],
)
def test_redis_str_iadd_operation_sanity(initial_value, other_value):
    # Arrange
    model = SimpleStringModel(name=initial_value)
    original_id = id(model.name)
    original_json_path = model.name.json_path

    # Act
    model.name += other_value
    expected = initial_value + other_value

    # Assert
    assert isinstance(model.name, RedisStr)
    assert str(model.name) == expected
    assert model.name.key == model.key
    assert model.name.field_path == ".name"
    assert id(model.name) != original_id
    assert model.name.json_path == original_json_path


def test_redis_bool_logical_operations_sanity():
    # Arrange
    model_true = SimpleBoolModel(flag=True)
    model_false = SimpleBoolModel(flag=False)

    # Act & Assert
    assert model_true.flag and True
    assert not (model_false.flag and True)
    assert model_true.flag or False
    assert not model_false.flag or True
    assert isinstance(model_true.flag, bool)
    assert isinstance(model_false.flag, bool)


@pytest.mark.parametrize(
    ["initial_value", "other_value"],
    [[b"hello", b" world"], [b"", b"test"], [b"\x00\x01", b"\x02\x03"]],
)
def test_redis_bytes_iadd_operation_sanity(initial_value, other_value):
    # Arrange
    model = SimpleBytesModel(data=initial_value)
    original_id = id(model.data)
    original_json_path = model.data.json_path

    # Act
    model.data += other_value
    expected = initial_value + other_value

    # Assert
    assert isinstance(model.data, RedisBytes)
    assert bytes(model.data) == expected
    assert model.data.key == model.key
    assert model.data.field_path == ".data"
    assert id(model.data) != original_id
    assert model.data.json_path == original_json_path


@pytest.mark.parametrize(
    ["initial_value", "other_value"],
    [[10, 5], [20, 8], [0, 15]],
)
def test_redis_int_iadd_operation_sanity(initial_value, other_value):
    # Arrange
    model = SimpleIntModel(count=initial_value)
    original_id = id(model.count)
    original_json_path = model.count.json_path

    # Act
    model.count += other_value
    expected = initial_value + other_value

    # Assert
    assert isinstance(model.count, RedisInt)
    assert int(model.count) == expected
    assert model.count.key == model.key
    assert model.count.field_path == ".count"
    assert id(model.count) != original_id
    assert model.count.json_path == original_json_path


@pytest.mark.parametrize(
    ["initial_value", "other_value"],
    [[20, 8], [15, 5], [100, 25]],
)
def test_redis_int_isub_operation_sanity(initial_value, other_value):
    # Arrange
    model = SimpleIntModel(count=initial_value)
    original_id = id(model.count)
    original_json_path = model.count.json_path

    # Act
    model.count -= other_value
    expected = initial_value - other_value

    # Assert
    assert isinstance(model.count, RedisInt)
    assert int(model.count) == expected
    assert model.count.key == model.key
    assert model.count.field_path == ".count"
    assert id(model.count) != original_id
    assert model.count.json_path == original_json_path


@pytest.mark.parametrize(
    ["initial_value", "other_value"],
    [[6, 4], [3, 7], [10, 2]],
)
def test_redis_int_imul_operation_sanity(initial_value, other_value):
    # Arrange
    model = SimpleIntModel(count=initial_value)
    original_id = id(model.count)
    original_json_path = model.count.json_path

    # Act
    model.count *= other_value
    expected = initial_value * other_value

    # Assert
    assert isinstance(model.count, RedisInt)
    assert int(model.count) == expected
    assert model.count.key == model.key
    assert model.count.field_path == ".count"
    assert id(model.count) != original_id
    assert model.count.json_path == original_json_path


@pytest.mark.parametrize(
    ["initial_value", "other_value"],
    [[15, 3], [20, 4], [100, 7]],
)
def test_redis_int_ifloordiv_operation_sanity(initial_value, other_value):
    # Arrange
    model = SimpleIntModel(count=initial_value)
    original_id = id(model.count)
    original_json_path = model.count.json_path

    # Act
    model.count //= other_value
    expected = initial_value // other_value

    # Assert
    assert isinstance(model.count, RedisInt)
    assert int(model.count) == expected
    assert model.count.key == model.key
    assert model.count.field_path == ".count"
    assert id(model.count) != original_id
    assert model.count.json_path == original_json_path


@pytest.mark.parametrize(
    ["initial_value", "other_value"],
    [[17, 5], [23, 7], [100, 9]],
)
def test_redis_int_imod_operation_sanity(initial_value, other_value):
    # Arrange
    model = SimpleIntModel(count=initial_value)
    original_id = id(model.count)
    original_json_path = model.count.json_path

    # Act
    model.count %= other_value
    expected = initial_value % other_value

    # Assert
    assert isinstance(model.count, RedisInt)
    assert int(model.count) == expected
    assert model.count.key == model.key
    assert model.count.field_path == ".count"
    assert id(model.count) != original_id
    assert model.count.json_path == original_json_path


@pytest.mark.parametrize(
    ["initial_value", "other_value"],
    [[2, 3], [3, 2], [5, 2]],
)
def test_redis_int_ipow_operation_sanity(initial_value, other_value):
    # Arrange
    model = SimpleIntModel(count=initial_value)
    original_id = id(model.count)
    original_json_path = model.count.json_path

    # Act
    model.count **= other_value
    expected = initial_value**other_value

    # Assert
    assert isinstance(model.count, RedisInt)
    assert int(model.count) == expected
    assert model.count.key == model.key
    assert model.count.field_path == ".count"
    assert id(model.count) != original_id
    assert model.count.json_path == original_json_path
