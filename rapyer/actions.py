from __future__ import annotations

import enum
import functools
import inspect
from typing import TYPE_CHECKING

from rapyer.context import _context_pipe

if TYPE_CHECKING:
    from rapyer import AtomicRedisModel
    from rapyer.config import RedisConfig


ACTION_GROUPS_ATTR = "_action_groups"


class ActionGroup(enum.Flag):
    """Categories of operations that can trigger TTL refresh."""

    READ = enum.auto()
    UPDATE = enum.auto()
    APPEND = enum.auto()
    DELETE = enum.auto()
    ARITHMETIC = enum.auto()

    @classmethod
    def all(cls) -> "ActionGroup":
        result = cls(0)
        for member in cls:
            result |= member
        return result


def mark_actions(*groups: ActionGroup):
    """Tag a method with action groups for TTL refresh.

    - For async methods, wraps the method so that it calls
      ``self.refresh_ttl_if_needed(action=combined)`` after execution.
    - For sync methods, only tags the method with ``ACTION_GROUPS_ATTR``;
      TTL refresh is deferred to pipeline-exit via ``should_refresh()``.

    Usage:
        @mark_actions(ActionGroup.UPDATE, ActionGroup.APPEND)
        async def aappend(self, item):
            ...

        @mark_actions(ActionGroup.UPDATE)
        def __setitem__(self, key, value):
            ...
    """
    combined = ActionGroup(0)
    for g in groups:
        combined |= g

    def decorator(method):
        setattr(method, ACTION_GROUPS_ATTR, combined)

        if not inspect.iscoroutinefunction(method):
            return method

        @functools.wraps(method)
        async def wrapper(self: "AtomicRedisModel", *args, **kwargs):
            result = await method(self, *args, **kwargs)
            await self.refresh_ttl_if_needed(action=combined)
            return result

        setattr(wrapper, ACTION_GROUPS_ATTR, combined)
        return wrapper

    return decorator


def marks_redis_updated(method):
    """Decorator for sync pipeline methods. Marks _redis_updated on the result.

    Pipeline TTL refresh is handled at pipeline exit via should_refresh(),
    not per-operation. This decorator only signals that Redis was modified.

    Usage:
        @marks_redis_updated
        def __iadd__(self, other):
            ...
    """

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        if result is not NotImplemented and _context_pipe.get() is not None:
            result._redis_updated = True
        return result

    return wrapper


def should_refresh_for_action(meta: "RedisConfig", action: "ActionGroup") -> bool:
    """Check whether the given action groups should trigger TTL refresh."""
    if meta.ttl is None:
        return False
    refresh = meta.refresh_ttl
    if refresh is True:
        return True
    if refresh is False:
        return False
    # refresh is an ActionGroup flag set
    return bool(refresh & action)
