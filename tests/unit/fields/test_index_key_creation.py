from typing import Annotated, get_args, get_origin

import pytest
from rapyer.fields.index import Index, IndexAnnotation
from rapyer.fields.key import Key, KeyAnnotation


def test_index_without_args_returns_index_annotation_sanity():
    # Arrange & Act
    result = Index()

    # Assert
    assert isinstance(result, IndexAnnotation)


def test_index_with_none_returns_index_annotation_sanity():
    # Arrange & Act
    result = Index(None)

    # Assert
    assert isinstance(result, IndexAnnotation)


@pytest.mark.parametrize(
    ["typ"],
    [
        [str],
        [int],
        [float],
        [bool],
    ],
)
def test_index_with_type_arg_returns_annotated_type_sanity(typ):
    # Arrange & Act
    result = Index(typ)

    # Assert
    assert get_origin(result) is Annotated
    args = get_args(result)
    assert args[0] is typ
    assert isinstance(args[1], IndexAnnotation)


@pytest.mark.parametrize(
    ["typ"],
    [
        [str],
        [int],
        [float],
        [bool],
    ],
)
def test_key_with_type_arg_returns_annotated_type_sanity(typ):
    # Arrange & Act
    result = Key(typ)

    # Assert
    assert get_origin(result) is Annotated
    args = get_args(result)
    assert args[0] is typ
    assert isinstance(args[1], KeyAnnotation)


def test_key_without_args_returns_key_annotation_sanity():
    # Arrange & Act
    result = Key()

    # Assert
    assert isinstance(result, KeyAnnotation)


def test_key_with_none_returns_key_annotation_sanity():
    # Arrange & Act
    result = Key(None)

    # Assert
    assert isinstance(result, KeyAnnotation)


@pytest.mark.parametrize(
    ["typ"],
    [
        [str],
        [int],
        [float],
        [bool],
    ],
)
def test_index_bracket_syntax_returns_annotated_type_sanity(typ):
    # Arrange & Act
    result = Index[typ]

    # Assert
    assert get_origin(result) is Annotated
    args = get_args(result)
    assert args[0] is typ
    assert isinstance(args[1], IndexAnnotation)


@pytest.mark.parametrize(
    ["typ"],
    [
        [str],
        [int],
        [float],
        [bool],
    ],
)
def test_key_bracket_syntax_returns_annotated_type_sanity(typ):
    # Arrange & Act
    result = Key[typ]

    # Assert
    assert get_origin(result) is Annotated
    args = get_args(result)
    assert args[0] is typ
    assert isinstance(args[1], KeyAnnotation)
