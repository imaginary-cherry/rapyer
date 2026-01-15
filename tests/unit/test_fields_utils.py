from typing import Type

import pytest

from rapyer.utils.fields import is_type_json_serializable
from tests.models.unknown_types import (
    StrStatus,
    IntPriority,
    PlainEnum,
)


@pytest.mark.parametrize(
    ["typ", "test_value", "expected"],
    [
        [StrStatus, StrStatus.ACTIVE, True],
        [StrStatus, StrStatus.INACTIVE, True],
        [IntPriority, IntPriority.LOW, True],
        [IntPriority, IntPriority.HIGH, True],
        [PlainEnum, PlainEnum.A, True],
        [str, "test", True],
        [int, 42, True],
        [float, 3.14, True],
        [bool, True, True],
        [list, [1, 2, 3], True],
        [dict, {"a": 1}, True],
        [type, str, False],
    ],
)
def test_is_type_json_serializable_with_value_sanity(typ, test_value, expected):
    # Act
    result = is_type_json_serializable(typ, test_value)

    # Assert
    assert result == expected


def test_is_type_json_serializable_without_test_value_sanity():
    # Arrange & Act
    result_str_enum = is_type_json_serializable(StrStatus, StrStatus.ACTIVE)
    result_int_enum = is_type_json_serializable(IntPriority, IntPriority.LOW)
    result_str = is_type_json_serializable(str, "str")

    # Assert
    assert result_str_enum is True
    assert result_int_enum is True
    assert result_str is True


def test_is_type_json_serializable_type_without_value_returns_false():
    # Arrange & Act
    result_type = is_type_json_serializable(type, int)
    result_type_str = is_type_json_serializable(Type[str], str)

    # Assert
    assert result_type is False
    assert result_type_str is False
