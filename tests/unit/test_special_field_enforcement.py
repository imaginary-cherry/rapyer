import inspect

import pytest

import tests.integration.special_types.test_priority_queue  # noqa: F401 - triggers decorator registration
import tests.integration.special_types.test_priority_queue_model_actions  # noqa: F401 - triggers decorator registration
import tests.unit.types.test_special_types  # noqa: F401 - triggers decorator registration
from rapyer.base import AtomicRedisModel
from tests.conftest import SPECIAL_FIELD_TESTED_METHODS

EXCLUDED_METHODS = [
    # Class setup - detects special fields during subclass init, not a runtime action
    AtomicRedisModel.__init_subclass__,
    AtomicRedisModel.redis_dump,
    AtomicRedisModel.redis_dump_json,
]


def method_to_tuple(method):
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)
    return class_name, method_name


EXCLUDED_FROM_SPECIAL_FIELD_TEST = {method_to_tuple(m) for m in EXCLUDED_METHODS}


def get_methods_with_special_field_handling():
    methods = []
    for name, method in inspect.getmembers(AtomicRedisModel):
        if name.startswith("__"):
            continue
        try:
            source = inspect.getsource(method)
        except (TypeError, OSError):
            continue
        if "_special_field_names" not in source:
            continue
        entry = (AtomicRedisModel.__name__, name)
        if entry not in EXCLUDED_FROM_SPECIAL_FIELD_TEST:
            methods.append(entry)
    return sorted(methods)


@pytest.mark.parametrize(
    ["class_name", "method_name"], get_methods_with_special_field_handling()
)
def test_method_has_special_field_test_coverage(class_name, method_name):
    # Arrange
    expected_entry = (class_name, method_name)

    # Act
    has_coverage = expected_entry in SPECIAL_FIELD_TESTED_METHODS

    # Assert
    assert has_coverage, (
        f"Method {class_name}.{method_name} has special field handling but no test.\n"
        f"Add @special_field_test_for({class_name}.{method_name}) to a test.\n"
        f"Or add to EXCLUDED_METHODS with justification."
    )
