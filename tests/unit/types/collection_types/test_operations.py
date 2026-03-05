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
from tests.models.unit_types import SimpleIntDictModel
from tests.unit.assertions import (
    assert_redis_dict_item_correct,
    assert_redis_list_correct_types,
    assert_redis_list_item_correct,
)


@pytest.mark.parametrize(
    "initial_items,new_item", [(["hello"], "world"), ([], "first"), (["a", "b"], "c")]
)
def test_redis_list_append_operation_sanity(initial_items, new_item):
    # Arrange
    model = SimpleListModel(items=initial_items)

    # Act - Test append operation
    model.items.append(new_item)

    # Assert
    assert isinstance(model.items, RedisList)
    assert len(model.items) == len(initial_items) + 1
    assert_redis_list_item_correct(
        model.items, -1, new_item, model.key, f".items[{len(initial_items)}]", RedisStr
    )


@pytest.mark.parametrize(
    "initial_items,extend_items",
    [
        (["hello"], ["world", "test"]),
        ([], ["first", "second"]),
        (["a"], ["b", "c", "d"]),
    ],
)
def test_redis_list_extend_operation_sanity(initial_items, extend_items):
    # Arrange
    model = SimpleListModel(items=initial_items)

    # Act - Test extend operation
    model.items.extend(extend_items)

    # Assert
    assert isinstance(model.items, RedisList)
    assert_redis_list_correct_types(model.items, model.key, ".items", RedisStr)


@pytest.mark.parametrize(
    "initial_items,index,new_item",
    [
        (["hello", "world"], 1, "new"),
        (["a", "b", "c"], 0, "start"),
        (["x"], 0, "replace"),
    ],
)
def test_redis_list_setitem_operation_sanity(initial_items, index, new_item):
    # Arrange
    model = SimpleListModel(items=initial_items)

    # Act - Test setitem operation
    model.items[index] = new_item

    # Assert
    assert isinstance(model.items, RedisList)
    assert_redis_list_item_correct(
        model.items, index, new_item, model.key, f".items[{index}]", RedisStr
    )


@pytest.mark.parametrize(
    "initial_numbers,increment_ops",
    [([1, 2, 3], [(0, 5), (1, 10)]), ([0], [(0, 1)]), ([10, 20], [(1, -5)])],
)
def test_redis_int_list_arithmetic_operations_sanity(initial_numbers, increment_ops):
    # Arrange
    model = SimpleIntListModel(numbers=initial_numbers)

    # Act & Assert
    for index, increment in increment_ops:
        original_value = int(model.numbers[index])
        result = model.numbers[index] + increment
        assert result == original_value + increment
        assert isinstance(model.numbers[index], RedisInt)


@pytest.mark.parametrize(
    "initial_data,new_key,new_value",
    [
        ({"key1": "value1"}, "key2", "value2"),
        ({}, "first", "value"),
        ({"existing": "old"}, "new", "fresh"),
    ],
)
def test_redis_dict_setitem_operation_sanity(initial_data, new_key, new_value):
    # Arrange
    model = SimpleDictModel(data=initial_data)

    # Act - Test setitem operation
    model.data[new_key] = new_value

    # Assert
    assert isinstance(model.data, RedisDict)
    assert_redis_dict_item_correct(
        model.data, new_key, new_value, model.key, f".data.{new_key}", RedisStr
    )


@pytest.mark.parametrize(
    "initial_data,update_data",
    [
        ({"key1": "value1"}, {"key2": "value2", "key3": "value3"}),
        ({}, {"first": "value", "second": "another"}),
        ({"existing": "old"}, {"existing": "updated", "new": "value"}),
    ],
)
def test_redis_dict_update_operation_sanity(initial_data, update_data):
    # Arrange
    model = SimpleDictModel(data=initial_data)

    # Act - Test update operation using |= operator
    model.data |= update_data

    # Assert
    assert isinstance(model.data, RedisDict)

    for key, value in update_data.items():
        assert_redis_dict_item_correct(
            model.data, key, value, model.key, f".data.{key}", RedisStr
        )


@pytest.mark.parametrize(
    "initial_counts,key,increment",
    [
        ({"count1": 10}, "count1", 5),
        ({"total": 0}, "total", 1),
        ({"score": 100}, "score", -10),
    ],
)
def test_redis_int_dict_arithmetic_operations_sanity(initial_counts, key, increment):
    # Arrange
    model = SimpleIntDictModel(counts=initial_counts)

    # Act & Assert
    original_value = int(model.counts[key])
    result = model.counts[key] + increment
    assert result == original_value + increment
    assert isinstance(model.counts[key], RedisInt)


def test_redis_list_clear_operation_sanity():
    # Arrange
    model = SimpleListModel(items=["hello", "world", "test"])

    # Act
    model.items.clear()

    # Assert
    assert isinstance(model.items, RedisList)
    assert len(model.items) == 0


def test_redis_dict_clear_operation_sanity():
    # Arrange
    model = SimpleDictModel(data={"key1": "value1", "key2": "value2"})

    # Act
    model.data.clear()

    # Assert
    assert isinstance(model.data, RedisDict)
    assert len(model.data) == 0


def test_redis_list_pop_operation_sanity():
    # Arrange
    model = SimpleListModel(items=["hello", "world", "test"])

    # Act
    popped = model.items.pop()

    # Assert
    assert isinstance(model.items, RedisList)
    assert len(model.items) == 2
    assert popped == "test"


def test_redis_dict_pop_operation_sanity():
    # Arrange
    model = SimpleDictModel(data={"key1": "value1", "key2": "value2"})

    # Act
    popped = model.data.pop("key1")

    # Assert
    assert isinstance(model.data, RedisDict)
    assert len(model.data) == 1
    assert "key1" not in model.data
    assert popped == "value1"


def test_redis_list_insert_operation_sanity():
    # Arrange
    model = SimpleListModel(items=["hello", "world"])

    # Act
    model.items.insert(1, "middle")

    # Assert
    assert isinstance(model.items, RedisList)
    assert len(model.items) == 3
    assert_redis_list_item_correct(
        model.items, 1, "middle", model.key, ".items[1]", RedisStr
    )


@pytest.mark.parametrize(
    "initial_items,extend_items",
    [
        (["hello"], ["world", "test"]),
        ([], ["first", "second"]),
        (["a"], ["b", "c", "d"]),
    ],
)
def test_redis_list_iadd_operation_sanity(initial_items, extend_items):
    # Arrange
    model = SimpleListModel(items=initial_items)

    # Act - Test += operator
    model.items += extend_items

    # Assert
    assert len(model.items) == len(initial_items) + len(extend_items)
    assert_redis_list_correct_types(model.items, model.key, ".items", RedisStr)


@pytest.mark.parametrize(
    "initial_items,delete_index",
    [
        (["hello", "world", "test"], 1),
        (["single"], 0),
        (["a", "b", "c"], -1),
    ],
)
def test_redis_list_delitem_operation_sanity(initial_items, delete_index):
    # Arrange
    model = SimpleListModel(items=initial_items)
    original_length = len(model.items)
    deleted_item = str(model.items[delete_index])

    # Act - Test del operation
    del model.items[delete_index]

    # Assert
    assert isinstance(model.items, RedisList)
    assert len(model.items) == original_length - 1

    # Verify the item was actually removed
    for item in model.items:
        assert str(item) != deleted_item or initial_items.count(deleted_item) > 1


def test_redis_dict_popitem_operation_sanity():
    # Arrange
    model = SimpleDictModel(data={"key1": "value1", "key2": "value2"})
    original_length = len(model.data)

    # Act
    popped_key, popped_value = model.data.popitem()

    # Assert
    assert isinstance(model.data, RedisDict)
    assert len(model.data) == original_length - 1
    assert popped_key not in model.data
    assert popped_value in ["value1", "value2"]


@pytest.mark.parametrize(
    "initial_data,delete_key",
    [
        ({"key1": "value1", "key2": "value2"}, "key1"),
        ({"single": "value"}, "single"),
        ({"a": "1", "b": "2", "c": "3"}, "b"),
    ],
)
def test_redis_dict_delitem_operation_sanity(initial_data, delete_key):
    # Arrange
    model = SimpleDictModel(data=initial_data)
    original_length = len(model.data)

    # Act - Test del operation
    del model.data[delete_key]

    # Assert
    assert isinstance(model.data, RedisDict)
    assert len(model.data) == original_length - 1
    assert delete_key not in model.data
