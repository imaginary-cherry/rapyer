import pytest

from tests.models.collection_types import (
    ComprehensiveTestModel,
    DictListModel,
    SimpleDictModel,
    SimpleListModel,
)
from tests.models.complex_types import ComplexNestedModel, NestedDictModel, OuterModel
from tests.models.simple_types import IntModel


@pytest.mark.asyncio
async def test_save_inner_list_field_only_sanity():
    # Arrange
    original_items = ["item1", "item2"]
    updated_items = ["new1", "new2", "new3"]

    model = SimpleListModel(items=original_items)
    await model.asave()

    # Modify the model but don't save the entire model
    model.items.extend(updated_items)  # This should NOT be saved

    # Act - Save only the items field with updated data
    await model.items.asave()

    # Assert
    retrieved_model = await SimpleListModel.aget(model.key)
    assert retrieved_model.items == original_items + updated_items


@pytest.mark.asyncio
async def test_save_inner_list_preserves_other_fields_sanity():
    # Arrange
    original_tags = ["tag1", "tag2"]
    original_metadata = {"key": "value"}
    original_name = "test"
    original_counter = 42

    updated_tags = ["new_tag1", "new_tag2", "new_tag3"]

    model = ComprehensiveTestModel(
        name=original_name,
        counter=original_counter,
        tags=original_tags,
        metadata=original_metadata,
    )
    await model.asave()

    # Modify other fields but DON'T save the entire model
    model.name = "should_not_be_saved"
    model.counter = 999
    model.metadata["extra"] = "not_saved"
    model.tags = updated_tags

    # Act - Save only the tag field
    await model.tags.asave()

    # Assert
    retrieved_model = await ComprehensiveTestModel.aget(model.key)
    assert retrieved_model.tags == updated_tags
    assert retrieved_model.name == original_name  # Should remain unchanged
    assert retrieved_model.counter == original_counter  # Should remain unchanged
    assert retrieved_model.metadata == original_metadata  # Should remain unchanged


@pytest.mark.asyncio
async def test_save_inner_dict_preserves_other_fields_sanity():
    # Arrange
    original_tags = ["tag1", "tag2"]
    original_metadata = {"key": "value"}
    original_name = "test"
    original_counter = 42

    updated_metadata = {"new_key": "new_value", "updated": "data"}

    model = ComprehensiveTestModel(
        name=original_name,
        counter=original_counter,
        tags=original_tags,
        metadata=original_metadata,
    )
    await model.asave()

    # Modify other fields but DON'T save the entire model
    model.name = "should_not_be_saved"
    model.counter = 999
    model.tags.append("not_saved")

    # Act - Save only the metadata field
    model.metadata.clear()
    model.metadata.update(updated_metadata)
    await model.metadata.asave()

    # Assert
    retrieved_model = await ComprehensiveTestModel.aget(model.key)
    assert retrieved_model.metadata == updated_metadata
    assert retrieved_model.name == original_name  # Should remain unchanged
    assert retrieved_model.counter == original_counter  # Should remain unchanged
    assert retrieved_model.tags == original_tags  # Should remain unchanged


@pytest.mark.asyncio
async def test_save_inner_dict_merge_operator_sanity():
    # Arrange
    original_data = {"key1": "value1", "key2": "value2"}
    additional_data = {"key3": "value3", "key4": "value4"}
    expected_result = {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
        "key4": "value4",
    }

    model = SimpleDictModel(data=original_data)
    await model.asave()

    # Act - Use |= operator to merge data and save only the dict field
    model.data |= additional_data
    await model.data.asave()

    # Assert
    retrieved_model = await SimpleDictModel.aget(model.key)
    assert retrieved_model.data == expected_result


@pytest.mark.asyncio
async def test_save_inner_dict_setitem_operation_sanity():
    # Arrange
    original_data = {"key1": "value1", "key2": "value2"}

    model = SimpleDictModel(data=original_data)
    await model.asave()

    # Act - Use setitem operations and save only the dict field
    model.data["key2"] = "updated_value2"
    model.data["new_key"] = "new_value"
    await model.data.asave()

    # Assert
    retrieved_model = await SimpleDictModel.aget(model.key)
    expected_result = {
        "key1": "value1",
        "key2": "updated_value2",
        "new_key": "new_value",
    }
    assert retrieved_model.data == expected_result


@pytest.mark.asyncio
async def test_save_inner_dict_pop_operation_sanity():
    # Arrange
    original_data = {"key1": "value1", "key2": "value2", "key3": "value3"}

    model = SimpleDictModel(data=original_data)
    await model.asave()

    # Act - Use pop operation and save only the dict field
    popped_value = model.data.pop("key2")
    await model.data.asave()

    # Assert
    retrieved_model = await SimpleDictModel.aget(model.key)
    expected_result = {"key1": "value1", "key3": "value3"}
    assert retrieved_model.data == expected_result
    assert popped_value == "value2"


@pytest.mark.asyncio
async def test_save_integer_field_add_operation_sanity():
    # Arrange
    original_count = 10
    add_value = 5
    expected_result = 15

    model = IntModel(count=original_count)
    await model.asave()

    # Modify other field but don't save the entire model
    model.score = 999  # Should not be saved

    # Act - Use += operator and save only the count field
    model.count += add_value
    await model.count.asave()

    # Assert
    retrieved_model = await IntModel.aget(model.key)
    assert retrieved_model.count == expected_result
    assert retrieved_model.score == 100  # Should remain unchanged


@pytest.mark.asyncio
async def test_save_integer_field_subtract_operation_sanity():
    # Arrange
    original_count = 20
    subtract_value = 7
    expected_result = 13

    model = IntModel(count=original_count)
    await model.asave()

    # Modify other field but don't save the entire model
    model.score = 999  # Should not be saved

    # Act - Use -= operator and save only the count field
    model.count -= subtract_value
    await model.count.asave()

    # Assert
    retrieved_model = await IntModel.aget(model.key)
    assert retrieved_model.count == expected_result
    assert retrieved_model.score == 100  # Should remain unchanged


@pytest.mark.asyncio
async def test_save_integer_field_multiply_operation_sanity():
    # Arrange
    original_count = 5
    multiply_value = 3
    expected_result = 15

    model = IntModel(count=original_count)
    await model.asave()

    # Modify other field but don't save the entire model
    model.score = 999  # Should not be saved

    # Act - Use *= operator and save only the count field
    model.count *= multiply_value
    await model.count.asave()

    # Assert
    retrieved_model = await IntModel.aget(model.key)
    assert retrieved_model.count == expected_result
    assert retrieved_model.score == 100  # Should remain unchanged


@pytest.mark.asyncio
async def test_save_integer_field_floor_divide_operation_sanity():
    # Arrange
    original_count = 17
    divide_value = 3
    expected_result = 5  # 17 // 3 = 5

    model = IntModel(count=original_count)
    await model.asave()

    # Modify other field but don't save the entire model
    model.score = 999  # Should not be saved

    # Act - Use //= operator and save only the count field
    model.count //= divide_value
    await model.count.asave()

    # Assert
    retrieved_model = await IntModel.aget(model.key)
    assert retrieved_model.count == expected_result
    assert retrieved_model.score == 100  # Should remain unchanged


@pytest.mark.asyncio
async def test_save_nested_list_item_sanity():
    # Arrange
    original_nested_dict = {
        "group1": {"item1": "value1"},
        "group2": {"item2": "value2"},
    }
    original_list_of_dicts = [{"key1": "val1"}, {"key2": "val2"}]
    original_dict_of_lists = {"list1": ["item1"], "list2": ["item2", "item3"]}

    updated_first_dict = {"key1": "updated_val1", "new_key": "new_value"}

    model = ComplexNestedModel(
        nested_list=[["a", "b"], ["c", "d"]],
        nested_dict=original_nested_dict,
        list_of_dicts=original_list_of_dicts,
        dict_of_lists=original_dict_of_lists,
    )
    await model.asave()

    # Modify other fields but don't save the entire model
    model.nested_dict["extra"] = {"not": "saved"}
    model.dict_of_lists["extra"] = ["not_saved"]

    # Act - Save only the first item in list_of_dicts
    model.list_of_dicts[0].clear()
    model.list_of_dicts[0].update(updated_first_dict)
    await model.list_of_dicts.asave()

    # Assert
    retrieved_model = await ComplexNestedModel.aget(model.key)
    expected_list_of_dicts = [updated_first_dict, {"key2": "val2"}]
    assert retrieved_model.list_of_dicts == expected_list_of_dicts
    assert retrieved_model.nested_dict == original_nested_dict
    assert retrieved_model.dict_of_lists == original_dict_of_lists


@pytest.mark.asyncio
async def test_save_nested_dict_key_sanity():
    # Arrange
    original_nested_dict = {
        "group1": {"item1": "value1"},
        "group2": {"item2": "value2"},
    }
    updated_nested_dict = {
        "group1": {"item1": "updated_value1", "new_item": "new_value"},
        "group2": {"item2": "value2"},
    }

    model = NestedDictModel(nested_dict=original_nested_dict)
    await model.asave()

    # Act - Modify nested_dict and save only the nested_dict field
    model.nested_dict["group1"]["item1"] = "updated_value1"
    model.nested_dict["group1"]["new_item"] = "new_value"
    await model.nested_dict.asave()

    # Assert
    retrieved_model = await NestedDictModel.aget(model.key)
    assert retrieved_model.nested_dict == updated_nested_dict


@pytest.mark.asyncio
async def test_save_nested_dict_list_item_sanity():
    # Arrange
    original_dict_of_lists = {"list1": ["item1", "item2"], "list2": ["item3", "item4"]}
    updated_dict_of_lists = {
        "list1": ["new_item1", "new_item2", "new_item3"],
        "list2": ["item3", "item4"],
    }

    model = ComplexNestedModel(
        nested_list=[["a"]],
        nested_dict={"g1": {"i1": "v1"}},
        list_of_dicts=[{"k1": "v1"}],
        dict_of_lists=original_dict_of_lists,
    )
    await model.asave()

    # Modify other fields but don't save the entire model
    model.nested_list.append(["not_saved"])
    model.list_of_dicts.append({"not": "saved"})

    # Act - Modify dict_of_lists and save only the dict_of_lists field
    model.dict_of_lists["list1"] = ["new_item1", "new_item2", "new_item3"]
    await model.dict_of_lists.asave()

    # Assert
    retrieved_model = await ComplexNestedModel.aget(model.key)
    assert retrieved_model.dict_of_lists == updated_dict_of_lists
    assert retrieved_model.nested_list == [["a"]]
    assert retrieved_model.list_of_dicts == [{"k1": "v1"}]


@pytest.mark.asyncio
async def test_save_deeply_nested_list_access_sanity():
    # Arrange
    original_list_of_dicts = [
        {"name": "item1", "value": "value1"},
        {"name": "item2", "value": "value2"},
    ]
    updated_list_of_dicts = [
        {"name": "updated1", "value": "updated_value1"},
        {"name": "item2", "value": "value2"},
    ]

    model = DictListModel(items=original_list_of_dicts)
    await model.asave()

    # Act - Modify items and save only the items field
    model.items[0]["name"] = "updated1"
    model.items[0]["value"] = "updated_value1"
    await model.items.asave()

    # Assert
    retrieved_model = await DictListModel.aget(model.key)
    assert retrieved_model.items == updated_list_of_dicts


@pytest.mark.asyncio
async def test_save_nested_inner_model_field_only_sanity():
    # Arrange
    original_inner_list = ["original1", "original2"]
    original_inner_counter = 5
    original_user_data = {"user1": 100}

    updated_inner_list = ["updated1", "updated2", "updated3"]

    model = OuterModel()
    model.middle_model.inner_model.lst = original_inner_list
    model.middle_model.inner_model.counter = original_inner_counter
    model.user_data = original_user_data
    await model.asave()

    # Modify other fields but DON'T save the entire model
    model.middle_model.inner_model.counter = 999  # Should not be saved
    model.user_data["extra"] = 999  # Should not be saved

    # Act - Save only the inner list field
    model.middle_model.inner_model.lst.extend(updated_inner_list)
    await model.middle_model.inner_model.lst.asave()

    # Assert
    retrieved_model = await OuterModel.aget(model.key)
    assert (
        retrieved_model.middle_model.inner_model.lst
        == original_inner_list + updated_inner_list
    )
    assert retrieved_model.middle_model.inner_model.counter == original_inner_counter
    assert retrieved_model.user_data == original_user_data


@pytest.mark.parametrize(
    "operation,initial_value,operand,expected",
    [
        ("+=", 10, 5, 15),
        ("-=", 20, 3, 17),
        ("*=", 4, 7, 28),
        ("//=", 25, 4, 6),
        ("%=", 17, 5, 2),
    ],
)
@pytest.mark.asyncio
async def test_save_integer_operations_parametrized_sanity(
    operation, initial_value, operand, expected
):
    # Arrange
    model = IntModel(count=initial_value)
    await model.asave()

    # Modify another field but don't save the entire model
    model.score = 999  # Should not be saved

    # Act - Apply operation and save only the count field
    if operation == "+=":
        model.count += operand
    elif operation == "-=":
        model.count -= operand
    elif operation == "*=":
        model.count *= operand
    elif operation == "//=":
        model.count //= operand
    elif operation == "%=":
        model.count %= operand

    await model.count.asave()

    # Assert
    retrieved_model = await IntModel.aget(model.key)
    assert retrieved_model.count == expected
    assert retrieved_model.score == 100  # Should remain unchanged


@pytest.mark.parametrize(
    "dict_operation,initial_data,operation_data,expected",
    [
        (
            "|=",
            {"a": "1", "b": "2"},
            {"c": "3", "d": "4"},
            {"a": "1", "b": "2", "c": "3", "d": "4"},
        ),
        (
            "update",
            {"a": "1", "b": "2"},
            {"b": "99", "c": "3"},
            {"a": "1", "b": "99", "c": "3"},
        ),
    ],
)
@pytest.mark.asyncio
async def test_save_dict_operations_parametrized_sanity(
    dict_operation, initial_data, operation_data, expected
):
    # Arrange
    model = SimpleDictModel(data=initial_data)
    await model.asave()

    # Act - Apply dict operation and save only the data field
    if dict_operation == "|=":
        model.data |= operation_data
    elif dict_operation == "update":
        model.data.update(operation_data)

    await model.data.asave()

    # Assert
    retrieved_model = await SimpleDictModel.aget(model.key)
    assert retrieved_model.data == expected


@pytest.mark.parametrize(
    "updated_data",
    [
        {"key1": "value1"},
        {"x": "y", "z": "w"},
        {},
    ],
)
@pytest.mark.asyncio
async def test_save_dict_field_parametrized_sanity(updated_data):
    # Arrange
    original_data = {"original_key": "original_value"}

    model = SimpleDictModel(data=original_data)
    await model.asave()

    # Act
    model.data.clear()
    model.data.update(updated_data)
    await model.data.asave()

    # Assert
    retrieved_model = await SimpleDictModel.aget(model.key)
    assert retrieved_model.data == updated_data
