from typing import Callable

TTL_TESTED_METHODS: set[tuple[str, str]] = set()


def tests_ttl_for(method: Callable):
    qualname = method.__qualname__
    class_name, method_name = qualname.rsplit(".", 1)

    def decorator(func):
        TTL_TESTED_METHODS.add((class_name, method_name))
        return func

    return decorator
