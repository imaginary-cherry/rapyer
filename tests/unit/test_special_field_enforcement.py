import pytest

import tests.integration.special_types.test_priority_queue  # noqa: F401 - triggers decorator registration
import tests.integration.special_types.test_priority_queue_model_actions  # noqa: F401 - triggers decorator registration
import tests.integration.special_types.test_ttl_priority_queue  # noqa: F401 - triggers decorator registration
from rapyer.base import AtomicRedisModel
from rapyer.types.special import SpecialFieldType
from tests.conftest import (
    SPECIAL_FIELD_TESTED_METHODS,
    SPECIAL_FIELD_TTL_TESTED_METHODS,
    get_async_methods,
)
from tests.unit.enforcement_exclusions import (
    MODEL_CHECK_METHODS,
    MODEL_INDEX_METHODS,
    MODEL_INTERNAL_METHODS,
)
from tests.unit.test_ttl_enforcement import EXCLUDED_FROM_TTL_TEST

EXCLUDED_FROM_SPECIAL_FIELD_TEST = (
    MODEL_CHECK_METHODS
    | MODEL_INDEX_METHODS  # Schema operations
    | MODEL_INTERNAL_METHODS  # Internal query helpers
)

EXCLUDED_FROM_SPECIAL_FIELD_TTL_TEST = (
    EXCLUDED_FROM_TTL_TEST | EXCLUDED_FROM_SPECIAL_FIELD_TEST
)


def collect_model_method_field_pairs(excluded):
    methods = sorted(m for m in get_async_methods(AtomicRedisModel) if m not in excluded)
    field_types = SpecialFieldType.__subclasses__()
    return [
        (class_name, method_name, ft.__name__)
        for class_name, method_name in methods
        for ft in field_types
    ]


@pytest.mark.parametrize(
    ["class_name", "method_name", "field_type_name"],
    collect_model_method_field_pairs(EXCLUDED_FROM_SPECIAL_FIELD_TTL_TEST),
)
def test_method_has_special_field_ttl_test_coverage(
    class_name, method_name, field_type_name
):
    # Arrange
    expected_entry = (class_name, method_name, field_type_name)

    # Act
    has_coverage = expected_entry in SPECIAL_FIELD_TTL_TESTED_METHODS

    # Assert
    assert has_coverage, (
        f"Method {class_name}.{method_name} needs a special field TTL test for {field_type_name}.\n"
        f"Add @special_field_ttl_test_for({class_name}.{method_name}, {field_type_name}) to a test.\n"
        f"Or add to the appropriate group in enforcement_exclusions.py with justification."
    )


@pytest.mark.parametrize(
    ["class_name", "method_name", "field_type_name"],
    collect_model_method_field_pairs(EXCLUDED_FROM_SPECIAL_FIELD_TEST),
)
def test_method_has_special_field_test_coverage(
    class_name, method_name, field_type_name
):
    # Arrange
    expected_entry = (class_name, method_name, field_type_name)

    # Act
    has_coverage = expected_entry in SPECIAL_FIELD_TESTED_METHODS

    # Assert
    assert has_coverage, (
        f"Method {class_name}.{method_name} needs a special field test for {field_type_name} "
        f"(i.e. check the method affect the special field).\n"
        f"Add @special_field_test_for({class_name}.{method_name}, {field_type_name}) to a test.\n"
        f"Or add to the appropriate group in enforcement_exclusions.py with justification."
    )
