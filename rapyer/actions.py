from __future__ import annotations

import enum
import functools
from typing import TYPE_CHECKING

from rapyer.context import _context_pipe

if TYPE_CHECKING:
    from rapyer import AtomicRedisModel
    from rapyer.config import RedisConfig


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


def refresh_action(*groups: ActionGroup):
    """Decorator that tags an async method with action groups for TTL refresh.

    Usage:
        @refresh_action(ActionGroup.UPDATE, ActionGroup.APPEND)
        async def aappend(self, item):
            ...
    """
    combined = ActionGroup(0)
    for g in groups:
        combined |= g

    def decorator(method):
        method._action_groups = combined

        @functools.wraps(method)
        async def wrapper(self: "AtomicRedisModel", *args, **kwargs):
            result = await method(self, *args, **kwargs)
            await self.refresh_ttl_if_needed(action=combined)
            return result

        wrapper._action_groups = combined
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


def pipeline_action(*groups: ActionGroup):
    """
    Decorator that tags a sync pipeline method with action groups.
    """
    combined = ActionGroup(0)
    for g in groups:
        combined |= g

    def decorator(method):
        method._action_groups = combined
        return method

    return decorator


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
