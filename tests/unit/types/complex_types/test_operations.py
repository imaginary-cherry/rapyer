import pytest
from rapyer.types.dct import RedisDict
from rapyer.types.lst import RedisList
from rapyer.types.string import RedisStr
from tests.models.complex_types import (
    DictOfListsModel,
    ListOfDictsModel,
    NestedDictModel,
    NestedListModel,
)


@pytest.mark.parametrize(
    "initial_nested,new_inner_list",
    [([["hello"]], ["world", "test"]), ([], ["first", "item"]), ([["a", "b"]], ["c"])],
)
def test_nested_list_append_operation_sanity(initial_nested, new_inner_list):
    # Arrange
    model = NestedListModel(nested_list=initial_nested)

    # Act - Append a new inner list
    model.nested_list.append(new_inner_list)

    # Assert
    assert isinstance(model.nested_list, RedisList)
    assert len(model.nested_list) == len(initial_nested) + 1

    new_inner = model.nested_list[-1]
    assert isinstance(new_inner, RedisList)
    assert new_inner.key == model.key
    assert len(new_inner) == len(new_inner_list)

    for i, item in enumerate(new_inner_list):
        assert isinstance(new_inner[i], RedisStr)
        assert str(new_inner[i]) == item
        assert new_inner[i].key == model.key


@pytest.mark.parametrize(
    "initial_nested,inner_index,new_item",
    [
        ([["hello", "world"]], 0, "test"),
        ([["a"], ["b"]], 1, "c"),
    ],
)
def test_nested_list_inner_append_operation_sanity(
    initial_nested, inner_index, new_item
):
    # Arrange
    model = NestedListModel(nested_list=initial_nested)

    # Act - Append to inner list
    model.nested_list[inner_index].append(new_item)

    # Assert
    inner_list = model.nested_list[inner_index]
    assert isinstance(inner_list, RedisList)
    assert isinstance(inner_list[-1], RedisStr)
    assert str(inner_list[-1]) == new_item
    assert inner_list[-1].key == model.key


@pytest.mark.parametrize(
    "initial_nested,outer_key,inner_dict",
    [
        ({"outer1": {"inner1": "value1"}}, "outer2", {"inner2": "value2"}),
        ({}, "first", {"key": "value"}),
    ],
)
def test_nested_dict_setitem_operation_sanity(initial_nested, outer_key, inner_dict):
    # Arrange
    model = NestedDictModel(nested_dict=initial_nested)

    # Act - Set new outer key with inner dict
    model.nested_dict[outer_key] = inner_dict

    # Assert
    assert isinstance(model.nested_dict, RedisDict)
    assert outer_key in model.nested_dict

    new_inner = model.nested_dict[outer_key]
    assert isinstance(new_inner, RedisDict)
    assert new_inner.key == model.key

    for key, value in inner_dict.items():
        assert isinstance(new_inner[key], RedisStr)
        assert str(new_inner[key]) == value
        assert new_inner[key].key == model.key


@pytest.mark.parametrize(
    "initial_nested,outer_key,inner_key,new_value",
    [
        ({"outer1": {"inner1": "old"}}, "outer1", "inner1", "new"),
        ({"outer1": {}}, "outer1", "inner2", "value"),
    ],
)
def test_nested_dict_inner_setitem_operation_sanity(
    initial_nested, outer_key, inner_key, new_value
):
    # Arrange
    model = NestedDictModel(nested_dict=initial_nested)

    # Act - Set inner dict item
    model.nested_dict[outer_key][inner_key] = new_value

    # Assert
    inner_dict = model.nested_dict[outer_key]
    assert isinstance(inner_dict, RedisDict)
    assert isinstance(inner_dict[inner_key], RedisStr)
    assert str(inner_dict[inner_key]) == new_value
    assert inner_dict[inner_key].key == model.key


@pytest.mark.parametrize(
    "initial_list,new_dict",
    [
        ([{"key1": "value1"}], {"key2": "value2"}),
        ([], {"first": "value"}),
    ],
)
def test_list_of_dicts_append_operation_sanity(initial_list, new_dict):
    # Arrange
    model = ListOfDictsModel(list_of_dicts=initial_list)

    # Act - Append new dict
    model.list_of_dicts.append(new_dict)

    # Assert
    assert isinstance(model.list_of_dicts, RedisList)
    assert len(model.list_of_dicts) == len(initial_list) + 1

    new_dict_obj = model.list_of_dicts[-1]
    assert isinstance(new_dict_obj, RedisDict)
    assert new_dict_obj.key == model.key

    for key, value in new_dict.items():
        assert isinstance(new_dict_obj[key], RedisStr)
        assert str(new_dict_obj[key]) == value
        assert new_dict_obj[key].key == model.key


@pytest.mark.parametrize(
    "initial_list,dict_index,new_key,new_value",
    [
        ([{"key1": "value1"}], 0, "key2", "value2"),
        ([{}, {"existing": "value"}], 1, "new", "item"),
    ],
)
def test_list_of_dicts_inner_setitem_operation_sanity(
    initial_list, dict_index, new_key, new_value
):
    # Arrange
    model = ListOfDictsModel(list_of_dicts=initial_list)

    # Act - Set item in dict within list
    model.list_of_dicts[dict_index][new_key] = new_value

    # Assert
    dict_obj = model.list_of_dicts[dict_index]
    assert isinstance(dict_obj, RedisDict)
    assert isinstance(dict_obj[new_key], RedisStr)
    assert str(dict_obj[new_key]) == new_value
    assert dict_obj[new_key].key == model.key


@pytest.mark.parametrize(
    "initial_dict,new_key,new_list",
    [
        ({"list1": ["a"]}, "list2", ["b", "c"]),
        ({}, "first", ["item"]),
    ],
)
def test_dict_of_lists_setitem_operation_sanity(initial_dict, new_key, new_list):
    # Arrange
    model = DictOfListsModel(dict_of_lists=initial_dict)

    # Act - Set new key with a list
    model.dict_of_lists[new_key] = new_list

    # Assert
    assert isinstance(model.dict_of_lists, RedisDict)
    assert new_key in model.dict_of_lists

    new_list_obj = model.dict_of_lists[new_key]
    assert isinstance(new_list_obj, RedisList)
    assert new_list_obj.key == model.key
    assert len(new_list_obj) == len(new_list)

    for i, item in enumerate(new_list):
        assert isinstance(new_list_obj[i], RedisStr)
        assert str(new_list_obj[i]) == item
        assert new_list_obj[i].key == model.key


@pytest.mark.parametrize(
    "initial_dict,list_key,new_item",
    [
        ({"list1": ["a", "b"]}, "list1", "c"),
        ({"empty": []}, "empty", "first"),
    ],
)
def test_dict_of_lists_inner_append_operation_sanity(initial_dict, list_key, new_item):
    # Arrange
    model = DictOfListsModel(dict_of_lists=initial_dict)

    # Act - Append to list within dict
    model.dict_of_lists[list_key].append(new_item)

    # Assert
    list_obj = model.dict_of_lists[list_key]
    assert isinstance(list_obj, RedisList)
    assert isinstance(list_obj[-1], RedisStr)
    assert str(list_obj[-1]) == new_item
    assert list_obj[-1].key == model.key


def test_nested_list_extend_operation_sanity():
    # Arrange
    model = NestedListModel(nested_list=[["hello"]])
    new_lists = [["world"], ["test", "item"]]

    # Act
    model.nested_list.extend(new_lists)

    # Assert
    assert isinstance(model.nested_list, RedisList)
    assert len(model.nested_list) == 3

    for i, expected_list in enumerate(new_lists, 1):
        inner_list = model.nested_list[i]
        assert isinstance(inner_list, RedisList)
        assert len(inner_list) == len(expected_list)

        for j, item in enumerate(expected_list):
            assert isinstance(inner_list[j], RedisStr)
            assert str(inner_list[j]) == item


def test_nested_dict_update_operation_sanity():
    # Arrange
    model = NestedDictModel(nested_dict={"outer1": {"inner1": "value1"}})
    update_data = {"outer2": {"inner2": "value2"}}

    # Act
    model.nested_dict |= update_data

    # Assert
    assert isinstance(model.nested_dict, RedisDict)
    assert "outer2" in model.nested_dict

    inner_dict = model.nested_dict["outer2"]
    assert isinstance(inner_dict, RedisDict)
    assert isinstance(inner_dict["inner2"], RedisStr)
    assert str(inner_dict["inner2"]) == "value2"


def test_nested_operations_preserve_types_and_keys_sanity():
    # Arrange
    model = NestedListModel(nested_list=[["initial"]])

    # Act - Multiple nested operations
    model.nested_list.append(["new", "list"])
    model.nested_list[0].append("added")
    model.nested_list[1][0] = "modified"

    # Assert
    assert isinstance(model.nested_list, RedisList)
    assert len(model.nested_list) == 2

    # Check first inner list
    assert isinstance(model.nested_list[0], RedisList)
    assert len(model.nested_list[0]) == 2
    assert str(model.nested_list[0][0]) == "initial"
    assert str(model.nested_list[0][1]) == "added"

    # Check second inner list
    assert isinstance(model.nested_list[1], RedisList)
    assert str(model.nested_list[1][0]) == "modified"
    assert str(model.nested_list[1][1]) == "list"

    # Verify all items have correct redis_key
    for i in range(len(model.nested_list)):
        assert model.nested_list[i].key == model.key
        for j in range(len(model.nested_list[i])):
            assert model.nested_list[i][j].key == model.key
