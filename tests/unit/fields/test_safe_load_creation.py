from typing import Annotated, get_args, get_origin

import pytest

from rapyer.fields.safe_load import SafeLoad, SafeLoadAnnotation


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
