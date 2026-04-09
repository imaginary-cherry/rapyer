import inspect
from typing import Callable

TTL_TESTED_METHODS: set[tuple[str, str]] = set()
TTL_NO_REFRESH_TESTED_METHODS: set[tuple[str, str]] = set()
SPECIAL_FIELD_TESTED_METHODS: set[tuple[str, str]] = set()
SPECIAL_FIELD_TTL_TESTED_METHODS: set[tuple[str, str]] = set()


def ttl_test_for(method: Callable):
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)

    def decorator(func):
        TTL_TESTED_METHODS.add((class_name, method_name))
        return func

    return decorator


def ttl_no_refresh_test_for(method: Callable):
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)

    def decorator(func):
        TTL_NO_REFRESH_TESTED_METHODS.add((class_name, method_name))
        return func

    return decorator


def special_field_test_for(method: Callable):
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)

    def decorator(func):
        SPECIAL_FIELD_TESTED_METHODS.add((class_name, method_name))
        return func

    return decorator


def special_field_ttl_test_for(method: Callable):
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)

    def decorator(func):
        SPECIAL_FIELD_TTL_TESTED_METHODS.add((class_name, method_name))
        return func

    return decorator


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
