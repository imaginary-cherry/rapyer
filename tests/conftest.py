import inspect
from typing import Callable

TTL_TESTED_METHODS: set[tuple[str, str]] = set()
TTL_NO_REFRESH_TESTED_METHODS: set[tuple[str, str]] = set()
SPECIAL_FIELD_TESTED_METHODS: set[tuple[str, str]] = set()
SPECIAL_FIELD_TTL_TESTED_METHODS: set[tuple[str, str]] = set()
BASE_MODEL_TTL_TESTED_METHODS: set[tuple[str, str]] = set()


def _make_coverage_decorator(coverage_set: set[tuple[str, str]]):
    def coverage_test_for(method: Callable):
        qualname = method.__qualname__
        class_name, method_name = qualname.rsplit(".", 1)

        def decorator(func):
            coverage_set.add((class_name, method_name))
            return func

        return decorator

    return coverage_test_for


ttl_test_for = _make_coverage_decorator(TTL_TESTED_METHODS)
ttl_no_refresh_test_for = _make_coverage_decorator(TTL_NO_REFRESH_TESTED_METHODS)
special_field_test_for = _make_coverage_decorator(SPECIAL_FIELD_TESTED_METHODS)
special_field_ttl_test_for = _make_coverage_decorator(SPECIAL_FIELD_TTL_TESTED_METHODS)
base_model_ttl_test_for = _make_coverage_decorator(BASE_MODEL_TTL_TESTED_METHODS)


def method_to_tuple(method: Callable) -> tuple[str, str]:
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)
    return class_name, method_name


def get_async_methods(cls):
    methods = []
    for name, method in inspect.getmembers(cls, predicate=inspect.iscoroutinefunction):
        if name.startswith("__"):
            continue
        if method.__qualname__.split(".")[0] != cls.__name__:
            continue
        methods.append((cls.__name__, name))
    return methods
