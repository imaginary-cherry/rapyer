import inspect
from typing import Callable

import pytest

import tests.integration.test_ttl_refresh  # noqa: F401 - triggers decorator registration
from rapyer.base import AtomicRedisModel
from rapyer.types import RedisInt
from rapyer.types.base import RedisType
from tests.conftest import TTL_TESTED_METHODS

EXCLUDED_METHODS = [
    # Deprecated methods
    AtomicRedisModel.delete,
    AtomicRedisModel.delete_by_key,
    AtomicRedisModel.duplicate,
    AtomicRedisModel.save,
    AtomicRedisModel.get,
    AtomicRedisModel.load,
    AtomicRedisModel.lock_from_key,
    AtomicRedisModel.lock,
    AtomicRedisModel.pipeline,
    RedisType.save,
    RedisType.load,
    RedisInt.increase,
    # Delete operations - key/item is removed
    AtomicRedisModel.adelete,
    AtomicRedisModel.adelete_by_key,
    AtomicRedisModel.adelete_many,
    # Methods that create NEW keys (get their own TTL via asave)
    AtomicRedisModel.aduplicate,
    AtomicRedisModel.duplicate_many,
    AtomicRedisModel.aduplicate_many,
    # Delegating methods (call other methods that handle TTL)
    AtomicRedisModel.afind_keys,
    AtomicRedisModel.acreate_index,
    AtomicRedisModel.adelete_index,
]


def method_to_tuple(method: Callable) -> tuple[str, str]:
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)
    return class_name, method_name


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
    return get_subclasses_recursive(RedisType)


def get_async_methods(cls):
    methods = []
    for name, method in inspect.getmembers(cls, predicate=inspect.iscoroutinefunction):
        if name.startswith("__"):
            continue
        if method.__qualname__.split(".")[0] != cls.__name__:
            continue
        methods.append((cls.__name__, name))
    return methods


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
