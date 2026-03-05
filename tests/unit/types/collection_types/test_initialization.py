import pytest
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.string import RedisStr
from tests.models.collection_types import (
    SimpleDictModel,
    SimpleIntListModel,
    SimpleListModel,
)
from tests.models.unit_types import MixedCollectionModel, SimpleIntDictModel


@pytest.mark.parametrize(
    "test_items", [["hello", "world"], ["item1", "item2", "item3"], [], ["single"]]
)
def test_redis_list_str_model_creation_sanity(test_items):
    # Arrange & Act
    model = SimpleListModel(items=test_items)

    # Assert
    assert isinstance(model.items, RedisList)
    assert model.items.key == model.key
    assert model.items.field_path == ".items"
    assert model.items.json_path == "$.items"
    assert len(model.items) == len(test_items)

    for i, item in enumerate(test_items):
        assert isinstance(model.items[i], RedisStr)
        assert str(model.items[i]) == item
        assert model.items[i].key == model.key
        assert model.items[i].field_path == f".items[{i}]"


@pytest.mark.parametrize("test_numbers", [[1, 2, 3], [0, -1, 100], [], [42]])
def test_redis_list_int_model_creation_sanity(test_numbers):
    # Arrange & Act
    model = SimpleIntListModel(numbers=test_numbers)

    # Assert
    assert isinstance(model.numbers, RedisList)
    assert model.numbers.key == model.key
    assert model.numbers.field_path == ".numbers"
    assert model.numbers.json_path == "$.numbers"
    assert len(model.numbers) == len(test_numbers)

    for i, number in enumerate(test_numbers):
        assert isinstance(model.numbers[i], RedisInt)
        assert int(model.numbers[i]) == number
        assert model.numbers[i].key == model.key
        assert model.numbers[i].field_path == f".numbers[{i}]"


@pytest.mark.parametrize(
    "test_data",
    [
        {"key1": "value1", "key2": "value2"},
        {"name": "John", "city": "NYC"},
        {},
        {"single": "value"},
    ],
)
def test_redis_dict_str_model_creation_sanity(test_data):
    # Arrange & Act
    model = SimpleDictModel(data=test_data)

    # Assert
    assert isinstance(model.data, RedisDict)
    assert model.data.key == model.key
    assert model.data.field_path == ".data"
    assert model.data.json_path == "$.data"
    assert len(model.data) == len(test_data)

    for key, value in test_data.items():
        assert key in model.data
        assert isinstance(model.data[key], RedisStr)
        assert str(model.data[key]) == value
        assert model.data[key].key == model.key
        assert model.data[key].field_path == f".data.{key}"


@pytest.mark.parametrize(
    "test_counts",
    [{"count1": 10, "count2": 20}, {"total": 100, "partial": 50}, {}, {"single": 42}],
)
def test_redis_dict_int_model_creation_sanity(test_counts):
    # Arrange & Act
    model = SimpleIntDictModel(counts=test_counts)

    # Assert
    assert isinstance(model.counts, RedisDict)
    assert model.counts.key == model.key
    assert model.counts.field_path == ".counts"
    assert model.counts.json_path == "$.counts"
    assert len(model.counts) == len(test_counts)

    for key, value in test_counts.items():
        assert key in model.counts
        assert isinstance(model.counts[key], RedisInt)
        assert int(model.counts[key]) == value
        assert model.counts[key].key == model.key
        assert model.counts[key].field_path == f".counts.{key}"


def test_mixed_collection_model_creation_sanity():
    # Arrange
    str_list_val = ["hello", "world"]
    int_list_val = [1, 2, 3]
    str_dict_val = {"name": "John", "city": "NYC"}
    int_dict_val = {"age": 30, "score": 100}

    # Act
    model = MixedCollectionModel(
        str_list=str_list_val,
        int_list=int_list_val,
        str_dict=str_dict_val,
        int_dict=int_dict_val,
    )

    # Assert
    assert isinstance(model.str_list, RedisList)
    assert isinstance(model.int_list, RedisList)
    assert isinstance(model.str_dict, RedisDict)
    assert isinstance(model.int_dict, RedisDict)

    assert model.str_list.key == model.key
    assert model.int_list.key == model.key
    assert model.str_dict.key == model.key
    assert model.int_dict.key == model.key

    assert model.str_list.field_path == ".str_list"
    assert model.int_list.field_path == ".int_list"
    assert model.str_dict.field_path == ".str_dict"
    assert model.int_dict.field_path == ".int_dict"

    for i, item in enumerate(str_list_val):
        assert isinstance(model.str_list[i], RedisStr)
        assert str(model.str_list[i]) == item

    for i, item in enumerate(int_list_val):
        assert isinstance(model.int_list[i], RedisInt)
        assert int(model.int_list[i]) == item

    for key, value in str_dict_val.items():
        assert isinstance(model.str_dict[key], RedisStr)
        assert str(model.str_dict[key]) == value

    for key, value in int_dict_val.items():
        assert isinstance(model.int_dict[key], RedisInt)
        assert int(model.int_dict[key]) == value


def test_empty_collections_model_creation_sanity():
    # Arrange & Act
    model = MixedCollectionModel()

    # Assert
    assert hasattr(model, "str_list")
    assert hasattr(model, "int_list")
    assert hasattr(model, "str_dict")
    assert hasattr(model, "int_dict")
