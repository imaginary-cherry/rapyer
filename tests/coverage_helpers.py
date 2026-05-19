from typing import Callable

from rapyer.actions import ACTION_GROUPS_ATTR, ActionGroup
from rapyer.types.base import BaseRedisType
from rapyer.types.special import SpecialFieldType


def cover_marker(*parts: str) -> str:
    return "cover_" + "_".join(parts)


COVER_PIPELINE_ATOM = cover_marker("pipeline_atom")
COVER_READ_IN_PIPELINE = cover_marker("read_in_pipeline")
COVER_TTL_REFRESH = cover_marker("ttl_refresh")
COVER_TTL_NO_REFRESH = cover_marker("ttl_no_refresh")
COVER_TTL_UPDATE_ONCE = cover_marker("ttl_update_once")
COVER_NO_CLOBBER = cover_marker("no_clobber")
COVER_ACTION_EFFECT = cover_marker("action_effect")
COVER_NO_TTL_WHEN_NOT_CONFIGURED = cover_marker("no_ttl_when_not_configured")
COVER_SYNC_NATIVE_EFFECT = cover_marker("sync_native_effect")

SPECIAL_FIELD_LIFECYCLE = "lifecycle"
SPECIAL_FIELD_TTL_REFRESH = "ttl_refresh"


def special_field_cover_marker(sf_class: type[SpecialFieldType], coverage: str) -> str:
    return cover_marker(sf_class.__name__, coverage)


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


def action_groups_for(covered_method) -> set[ActionGroup]:
    groups: set[ActionGroup] = set()
    for method in covered_methods_as_list(covered_method):
        method_groups = getattr(method, ACTION_GROUPS_ATTR, None)
        if method_groups:
            groups |= {member for member in ActionGroup if member & method_groups}
    return groups


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
