from typing import Callable

TTL_TESTED_METHODS: set[tuple[str, str]] = set()
TTL_NO_REFRESH_TESTED_METHODS: set[tuple[str, str]] = set()


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
