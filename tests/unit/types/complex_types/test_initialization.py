import pytest
from rapyer.types.dct import RedisDict
from rapyer.types.lst import RedisList
from rapyer.types.string import RedisStr
from tests.models.complex_types import (
    ComplexNestedModel,
    DictOfListsModel,
    ListOfDictsModel,
    NestedDictModel,
    NestedListModel,
    TripleNestedModel,
)


@pytest.mark.parametrize(
    "test_nested_list",
    [
        [["hello", "world"], ["foo", "bar"]],
        [[], ["single"]],
        [["a", "b", "c"], ["x", "y"]],
        [],
    ],
)
def test_nested_list_model_creation_sanity(test_nested_list):
    # Arrange & Act
    model = NestedListModel(nested_list=test_nested_list)

    # Assert
    assert isinstance(model.nested_list, RedisList)
    assert model.nested_list.key == model.key
    assert model.nested_list.field_path == ".nested_list"
    assert model.nested_list.json_path == "$.nested_list"
    assert len(model.nested_list) == len(test_nested_list)

    for i, inner_list in enumerate(test_nested_list):
        assert isinstance(model.nested_list[i], RedisList)
        assert model.nested_list[i].key == model.key
        assert model.nested_list[i].field_path == f".nested_list[{i}]"
        assert len(model.nested_list[i]) == len(inner_list)

        for j, item in enumerate(inner_list):
            assert isinstance(model.nested_list[i][j], RedisStr)
            assert str(model.nested_list[i][j]) == item
            assert model.nested_list[i][j].key == model.key
            assert model.nested_list[i][j].field_path == f".nested_list[{i}][{j}]"


@pytest.mark.parametrize(
    "test_nested_dict",
    [
        {"outer1": {"inner1": "value1", "inner2": "value2"}},
        {"outer1": {}, "outer2": {"inner1": "value1"}},
        {},
        {"single": {"key": "value"}},
    ],
)
def test_nested_dict_model_creation_sanity(test_nested_dict):
    # Arrange & Act
    model = NestedDictModel(nested_dict=test_nested_dict)

    # Assert
    assert isinstance(model.nested_dict, RedisDict)
    assert model.nested_dict.key == model.key
    assert model.nested_dict.field_path == ".nested_dict"
    assert model.nested_dict.json_path == "$.nested_dict"
    assert len(model.nested_dict) == len(test_nested_dict)

    for outer_key, inner_dict in test_nested_dict.items():
        assert isinstance(model.nested_dict[outer_key], RedisDict)
        assert model.nested_dict[outer_key].key == model.key
        assert model.nested_dict[outer_key].field_path == f".nested_dict.{outer_key}"
        assert len(model.nested_dict[outer_key]) == len(inner_dict)

        for inner_key, value in inner_dict.items():
            assert isinstance(model.nested_dict[outer_key][inner_key], RedisStr)
            assert str(model.nested_dict[outer_key][inner_key]) == value
            assert model.nested_dict[outer_key][inner_key].key == model.key
            assert (
                model.nested_dict[outer_key][inner_key].field_path
                == f".nested_dict.{outer_key}.{inner_key}"
            )


@pytest.mark.parametrize(
    "test_list_of_dicts",
    [
        [{"key1": "value1"}, {"key2": "value2"}],
        [{}],
        [],
        [{"name": "John", "age": "30"}, {"name": "Jane", "city": "NYC"}],
    ],
)
def test_list_of_dicts_model_creation_sanity(test_list_of_dicts):
    # Arrange & Act
    model = ListOfDictsModel(list_of_dicts=test_list_of_dicts)

    # Assert
    assert isinstance(model.list_of_dicts, RedisList)
    assert model.list_of_dicts.key == model.key
    assert model.list_of_dicts.field_path == ".list_of_dicts"
    assert len(model.list_of_dicts) == len(test_list_of_dicts)

    for i, dict_item in enumerate(test_list_of_dicts):
        assert isinstance(model.list_of_dicts[i], RedisDict)
        assert model.list_of_dicts[i].key == model.key
        assert model.list_of_dicts[i].field_path == f".list_of_dicts[{i}]"
        assert len(model.list_of_dicts[i]) == len(dict_item)

        for key, value in dict_item.items():
            assert isinstance(model.list_of_dicts[i][key], RedisStr)
            assert str(model.list_of_dicts[i][key]) == value
            assert model.list_of_dicts[i][key].key == model.key
            assert (
                model.list_of_dicts[i][key].field_path == f".list_of_dicts[{i}].{key}"
            )


@pytest.mark.parametrize(
    "test_dict_of_lists",
    [
        {"list1": ["a", "b"], "list2": ["c", "d"]},
        {"empty": [], "single": ["item"]},
        {},
        {"names": ["John", "Jane"], "cities": ["NYC", "LA"]},
    ],
)
def test_dict_of_lists_model_creation_sanity(test_dict_of_lists):
    # Arrange & Act
    model = DictOfListsModel(dict_of_lists=test_dict_of_lists)

    # Assert
    assert isinstance(model.dict_of_lists, RedisDict)
    assert model.dict_of_lists.key == model.key
    assert model.dict_of_lists.field_path == ".dict_of_lists"
    assert len(model.dict_of_lists) == len(test_dict_of_lists)

    for key, list_value in test_dict_of_lists.items():
        assert isinstance(model.dict_of_lists[key], RedisList)
        assert model.dict_of_lists[key].key == model.key
        assert model.dict_of_lists[key].field_path == f".dict_of_lists.{key}"
        assert len(model.dict_of_lists[key]) == len(list_value)

        for i, item in enumerate(list_value):
            assert isinstance(model.dict_of_lists[key][i], RedisStr)
            assert str(model.dict_of_lists[key][i]) == item
            assert model.dict_of_lists[key][i].key == model.key
            assert (
                model.dict_of_lists[key][i].field_path == f".dict_of_lists.{key}[{i}]"
            )


def test_complex_nested_model_creation_sanity():
    # Arrange
    nested_list_val = [["hello", "world"], ["foo", "bar"]]
    nested_dict_val = {"outer1": {"inner1": "value1"}}
    list_of_dicts_val = [{"key1": "value1"}, {"key2": "value2"}]
    dict_of_lists_val = {"list1": ["a", "b"]}

    # Act
    model = ComplexNestedModel(
        nested_list=nested_list_val,
        nested_dict=nested_dict_val,
        list_of_dicts=list_of_dicts_val,
        dict_of_lists=dict_of_lists_val,
    )

    # Assert
    assert isinstance(model.nested_list, RedisList)
    assert isinstance(model.nested_dict, RedisDict)
    assert isinstance(model.list_of_dicts, RedisList)
    assert isinstance(model.dict_of_lists, RedisDict)

    assert model.nested_list.key == model.key
    assert model.nested_dict.key == model.key
    assert model.list_of_dicts.key == model.key
    assert model.dict_of_lists.key == model.key

    assert model.nested_list.field_path == ".nested_list"
    assert model.nested_dict.field_path == ".nested_dict"
    assert model.list_of_dicts.field_path == ".list_of_dicts"
    assert model.dict_of_lists.field_path == ".dict_of_lists"


@pytest.mark.parametrize(
    "test_triple_list", [[[["a", "b"], ["c"]], [["d"], ["e", "f"]]], [[[]]], []]
)
def test_triple_nested_list_model_creation_sanity(test_triple_list):
    # Arrange & Act
    model = TripleNestedModel(triple_list=test_triple_list)

    # Assert
    assert isinstance(model.triple_list, RedisList)
    assert model.triple_list.key == model.key
    assert model.triple_list.field_path == ".triple_list"
    assert len(model.triple_list) == len(test_triple_list)

    for i, level2_list in enumerate(test_triple_list):
        assert isinstance(model.triple_list[i], RedisList)
        assert model.triple_list[i].key == model.key
        assert model.triple_list[i].field_path == f".triple_list[{i}]"

        for j, level3_list in enumerate(level2_list):
            assert isinstance(model.triple_list[i][j], RedisList)
            assert model.triple_list[i][j].key == model.key
            assert model.triple_list[i][j].field_path == f".triple_list[{i}][{j}]"

            for k, item in enumerate(level3_list):
                assert isinstance(model.triple_list[i][j][k], RedisStr)
                assert str(model.triple_list[i][j][k]) == item
                assert model.triple_list[i][j][k].key == model.key
                assert (
                    model.triple_list[i][j][k].field_path
                    == f".triple_list[{i}][{j}][{k}]"
                )
