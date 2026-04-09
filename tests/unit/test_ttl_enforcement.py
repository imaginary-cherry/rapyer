import pytest

import tests.integration.special_types.test_ttl_priority_queue  # noqa: F401 - triggers decorator registration
import tests.integration.test_ttl_refresh  # noqa: F401 - triggers decorator registration
from rapyer.base import AtomicRedisModel
from rapyer.types.base import BaseRedisType, RedisType
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.special import SpecialFieldType
from tests.conftest import (
    TTL_NO_REFRESH_TESTED_METHODS,
    TTL_TESTED_METHODS,
    get_async_methods,
    method_to_tuple,
)

EXCLUDED_METHODS = [
    # Delete operations - key/item is removed
    AtomicRedisModel.adelete,
    AtomicRedisModel.adelete_by_key,
    AtomicRedisModel.adelete_many,
    # Methods that create NEW keys (get their own TTL via asave)
    AtomicRedisModel.aduplicate,
    AtomicRedisModel.aduplicate_many,
    # Existence check - no data access, no TTL refresh needed
    AtomicRedisModel.aexists,
    # Delegating methods (call other methods that handle TTL)
    AtomicRedisModel.afind_keys,
    AtomicRedisModel.acreate_index,
    AtomicRedisModel.adelete_index,
    # TTL operations - this method IS the TTL operation itself
    AtomicRedisModel.aset_ttl,
    AtomicRedisModel.refresh_ttl_if_needed,
    RedisType.refresh_ttl_if_needed,
    # Inner methods
    AtomicRedisModel._search_keys_by_query,
    # PQ: read-only operations — no data mutation, no TTL refresh needed
    RedisPriorityQueue.apeek,
    RedisPriorityQueue.asize,
    RedisPriorityQueue.aitems,
    # PQ: save is a no-op, delete removes the key
    RedisPriorityQueue.asave_special,
    RedisPriorityQueue.adelete_special,
    # SpecialFieldType: abstract methods — covered by concrete subclass exclusions
    SpecialFieldType.asave_special,
    SpecialFieldType.adelete_special,
]


EXCLUDED_FROM_TTL_TEST = {method_to_tuple(m) for m in EXCLUDED_METHODS}


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
