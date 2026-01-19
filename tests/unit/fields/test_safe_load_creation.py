from typing import Annotated, get_args, get_origin

import pytest

from rapyer.fields.safe_load import SafeLoad, SafeLoadAnnotation
from tests.models.safe_load_types import (
    ModelWithMixedListFields,
    ModelWithMixedDictFields,
)


def test_safe_load_without_args_returns_safe_load_annotation_sanity():
    # Arrange & Act
    result = SafeLoad()

    # Assert
    assert isinstance(result, SafeLoadAnnotation)


def test_safe_load_with_none_returns_safe_load_annotation_sanity():
    # Arrange & Act
    result = SafeLoad(None)

    # Assert
    assert isinstance(result, SafeLoadAnnotation)


@pytest.mark.parametrize(
    ["typ"],
    [
        [str],
        [int],
        [type],
        [list],
    ],
)
def test_safe_load_with_type_arg_returns_annotated_type_sanity(typ):
    # Arrange & Act
    result = SafeLoad(typ)

    # Assert
    assert get_origin(result) is Annotated
    args = get_args(result)
    assert args[0] is typ
    assert isinstance(args[1], SafeLoadAnnotation)


@pytest.mark.parametrize(
    ["typ"],
    [
        [str],
        [int],
        [type],
        [list],
    ],
)
def test_safe_load_bracket_syntax_returns_annotated_type_sanity(typ):
    # Arrange & Act
    result = SafeLoad[typ]

    # Assert
    assert get_origin(result) is Annotated
    args = get_args(result)
    assert args[0] is typ
    assert isinstance(args[1], SafeLoadAnnotation)


def test_safe_list_field_has_safe_load_true_sanity():
    # Arrange
    model = ModelWithMixedListFields()

    # Act
    safe_list_type = type(model.safe_list)

    # Assert
    assert safe_list_type.safe_load is True


def test_unsafe_list_field_has_safe_load_false_sanity():
    # Arrange
    model = ModelWithMixedListFields()

    # Act
    unsafe_list_type = type(model.unsafe_list)

    # Assert
    assert unsafe_list_type.safe_load is False


def test_safe_dict_field_has_safe_load_true_sanity():
    # Arrange
    model = ModelWithMixedDictFields()

    # Act
    safe_dict_type = type(model.safe_dict)

    # Assert
    assert safe_dict_type.safe_load is True


def test_unsafe_dict_field_has_safe_load_false_sanity():
    # Arrange
    model = ModelWithMixedDictFields()

    # Act
    unsafe_dict_type = type(model.unsafe_dict)

    # Assert
    assert unsafe_dict_type.safe_load is False


def test_assign_safe_list_to_unsafe_list_unsafe_stays_unsafe():
    # Arrange
    model = ModelWithMixedListFields(safe_list=[1, 2, 3], unsafe_list=[])

    # Act
    model.unsafe_list = model.safe_list

    # Assert
    unsafe_list_type = type(model.unsafe_list)
    assert unsafe_list_type.safe_load is False


def test_assign_unsafe_list_to_safe_list_safe_stays_safe():
    # Arrange
    model = ModelWithMixedListFields(safe_list=[], unsafe_list=[1, 2, 3])

    # Act
    model.safe_list = model.unsafe_list

    # Assert
    safe_list_type = type(model.safe_list)
    assert safe_list_type.safe_load is True


def test_assign_safe_dict_to_unsafe_dict_unsafe_stays_unsafe():
    # Arrange
    model = ModelWithMixedDictFields(safe_dict={"a": 1}, unsafe_dict={})

    # Act
    model.unsafe_dict = model.safe_dict

    # Assert
    unsafe_dict_type = type(model.unsafe_dict)
    assert unsafe_dict_type.safe_load is False


def test_assign_unsafe_dict_to_safe_dict_safe_stays_safe():
    # Arrange
    model = ModelWithMixedDictFields(safe_dict={}, unsafe_dict={"a": 1})

    # Act
    model.safe_dict = model.unsafe_dict

    # Assert
    safe_dict_type = type(model.safe_dict)
    assert safe_dict_type.safe_load is True
