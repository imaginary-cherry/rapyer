import pytest

import tests.integration.special_types.test_priority_queue  # noqa: F401 - triggers decorator registration
import tests.integration.special_types.test_priority_queue_model_actions  # noqa: F401 - triggers decorator registration
import tests.integration.special_types.test_ttl_priority_queue  # noqa: F401 - triggers decorator registration
from rapyer.base import AtomicRedisModel
from tests.conftest import (
    SPECIAL_FIELD_TESTED_METHODS,
    SPECIAL_FIELD_TTL_TESTED_METHODS,
    get_async_methods,
    method_to_tuple,
)

EXCLUDED_METHODS = [
    # Class setup - detects special fields during subclass init, not a runtime action
    AtomicRedisModel.__init_subclass__,
    AtomicRedisModel.redis_dump,
    AtomicRedisModel.redis_dump_json,
]


EXCLUDED_FROM_SPECIAL_FIELD_TEST = {method_to_tuple(m) for m in EXCLUDED_METHODS}


EXCLUDED_TTL_METHODS = [
    *EXCLUDED_METHODS,
    # Delete operations - key is removed, no TTL refresh
    AtomicRedisModel.adelete,
    # Methods that create NEW keys (get their own TTL via asave)
    AtomicRedisModel.aduplicate,
]

EXCLUDED_FROM_SPECIAL_FIELD_TTL_TEST = {method_to_tuple(m) for m in EXCLUDED_TTL_METHODS}


def collect_model_methods(excluded):
    return sorted(
        m for m in get_async_methods(AtomicRedisModel) if m not in excluded
    )


@pytest.mark.parametrize(["class_name", "method_name"], collect_model_methods(EXCLUDED_FROM_SPECIAL_FIELD_TTL_TEST))
def test_method_has_special_field_ttl_test_coverage(class_name, method_name):
    # Arrange
    expected_entry = (class_name, method_name)

    # Act
    has_coverage = expected_entry in SPECIAL_FIELD_TTL_TESTED_METHODS

    # Assert
    assert has_coverage, (
        f"Method {class_name}.{method_name} needs a special field TTL test.\n"
        f"Add @special_field_ttl_test_for({class_name}.{method_name}) to a test.\n"
        f"Or add to EXCLUDED_TTL_METHODS with justification."
    )


@pytest.mark.parametrize(["class_name", "method_name"], collect_model_methods(EXCLUDED_FROM_SPECIAL_FIELD_TEST))
def test_method_has_special_field_test_coverage(class_name, method_name):
    # Arrange
    expected_entry = (class_name, method_name)

    # Act
    has_coverage = expected_entry in SPECIAL_FIELD_TESTED_METHODS

    # Assert
    assert has_coverage, (
        f"Method {class_name}.{method_name} needs a special field test.\n"
        f"Add @special_field_test_for({class_name}.{method_name}) to a test.\n"
        f"Or add to EXCLUDED_METHODS with justification."
    )
