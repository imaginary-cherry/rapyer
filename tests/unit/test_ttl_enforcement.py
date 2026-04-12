import pytest

import tests.integration.special_types.test_ttl_priority_queue  # noqa: F401 - triggers decorator registration
import tests.integration.test_ttl_refresh  # noqa: F401 - triggers decorator registration
from rapyer.base import AtomicRedisModel
from rapyer.types.base import BaseRedisType
from rapyer.types.special import SpecialFieldType
from tests.conftest import (
    BASE_MODEL_TTL_TESTED_METHODS,
    TTL_NO_REFRESH_TESTED_METHODS,
    TTL_TESTED_METHODS,
    get_async_methods,
)
from tests.unit.enforcement_exclusions import (
    MODEL_DELETE_METHODS,
    MODEL_DUPLICATE_METHODS,
    MODEL_INDEX_METHODS,
    MODEL_INTERNAL_METHODS,
    MODEL_TTL_METHODS,
    PQ_LIFECYCLE_METHODS,
    SPECIAL_FIELD_ABSTRACT_METHODS,
    TTL_REFRESH_METHODS,
)

EXCLUDED_FROM_TTL_TEST = (
    MODEL_DELETE_METHODS  # Key removed, no TTL to refresh
    | MODEL_DUPLICATE_METHODS  # New keys get own TTL via asave
    | MODEL_INDEX_METHODS  # Delegate to other methods
    | MODEL_TTL_METHODS  # IS the TTL setter
    | MODEL_INTERNAL_METHODS  # Internal query helpers
    | TTL_REFRESH_METHODS  # IS the TTL refresh mechanism
    | PQ_LIFECYCLE_METHODS  # Save no-op, delete removes key
    | SPECIAL_FIELD_ABSTRACT_METHODS  # Abstract, covered by concrete subclass
)


def get_subclasses_recursive(cls):
    result = []
    for subclass in cls.__subclasses__():
        module = getattr(subclass, "__module__", "")
        if "test" not in module.lower():
            result.append(subclass)
            result.extend(get_subclasses_recursive(subclass))
    return result


def get_all_redis_subclasses():
    return get_subclasses_recursive(BaseRedisType)


def collect_all_methods():
    all_methods = set()
    for cls in get_all_redis_subclasses():
        all_methods.update(get_async_methods(cls))
    all_methods.update(get_async_methods(AtomicRedisModel))
    return sorted([m for m in all_methods if m not in EXCLUDED_FROM_TTL_TEST])


def collect_special_field_methods():
    all_methods = set()
    for cls in get_subclasses_recursive(SpecialFieldType):
        all_methods.update(get_async_methods(cls))
    return sorted([m for m in all_methods if m not in EXCLUDED_FROM_TTL_TEST])


@pytest.mark.parametrize(["class_name", "method_name"], collect_special_field_methods())
def test_special_field_method_has_base_model_ttl_test_coverage(class_name, method_name):
    # Arrange
    expected_entry = (class_name, method_name)

    # Act
    has_coverage = expected_entry in BASE_MODEL_TTL_TESTED_METHODS

    # Assert
    assert has_coverage, (
        f"Method {class_name}.{method_name} needs a base model TTL test.\n"
        f"Add @base_model_ttl_test_for({class_name}.{method_name}) to a test.\n"
        f"Or add to EXCLUDED_FROM_TTL_TEST with justification."
    )


@pytest.mark.parametrize(["class_name", "method_name"], collect_all_methods())
def test_method_has_ttl_test_coverage(class_name, method_name):
    # Arrange
    expected_entry = (class_name, method_name)

    # Act
    has_coverage = expected_entry in TTL_TESTED_METHODS

    # Assert
    assert has_coverage, (
        f"Method {class_name}.{method_name} needs a TTL test.\n"
        f"Add @ttl_test_for({class_name}.{method_name}) to a test in test_ttl_refresh.py\n"
        f"Or add to EXCLUDED_FROM_TTL_TEST with justification."
    )


@pytest.mark.parametrize(["class_name", "method_name"], collect_all_methods())
def test_method_has_ttl_no_refresh_test_coverage(class_name, method_name):
    # Arrange
    expected_entry = (class_name, method_name)

    # Act
    has_coverage = expected_entry in TTL_NO_REFRESH_TESTED_METHODS

    # Assert
    assert has_coverage, (
        f"Method {class_name}.{method_name} needs a TTL no-refresh test.\n"
        f"Add @ttl_no_refresh_test_for({class_name}.{method_name}) to a test in test_ttl_refresh.py\n"
        f"Or add to EXCLUDED_FROM_TTL_TEST with justification."
    )
