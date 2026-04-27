from typing import Callable

from rapyer.actions import ACTION_GROUPS_ATTR, ActionGroup
from rapyer.types.base import BaseRedisType


def cover_tuple(method: Callable) -> tuple[str, str]:
    qualname = getattr(method, "__qualname__", getattr(method, "__name__", ""))
    if "." in qualname:
        cls_name, method_name = qualname.rsplit(".", 1)
        return cls_name, method_name
    return "rapyer", qualname


def all_subclasses(cls: type) -> set[type]:
    result = set()
    for sub in cls.__subclasses__():
        result.add(sub)
        result.update(all_subclasses(sub))
    return result


def should_ignore_group(
    method: Callable, ignore_groups: ActionGroup | None = None
) -> bool:
    if ignore_groups is None:
        return False

    groups = getattr(method, ACTION_GROUPS_ATTR, None)
    if groups is None:
        return False

    return bool(groups & ignore_groups)


def covered_methods_as_list(covered_method) -> list:
    if covered_method is None:
        return []
    if isinstance(covered_method, list):
        return covered_method
    return [covered_method]


def is_base_redis_type_method(method: Callable) -> bool:
    redis_type_names = {
        BaseRedisType.__name__,
        *(cls.__name__ for cls in all_subclasses(BaseRedisType)),
    }
    class_name, _ = cover_tuple(method)
    return class_name in redis_type_names


def is_action_for_refresh_sf(covered_method) -> bool:
    for method in covered_methods_as_list(covered_method):
        if should_ignore_group(method, ActionGroup.DELETE):
            return False
        if is_base_redis_type_method(method):
            return False
    return True
