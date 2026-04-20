from __future__ import annotations

import contextvars
import enum
import functools
import inspect
from typing import TYPE_CHECKING, Optional

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


class TargetSource(enum.Enum):
    """How the ``mark_actions`` decorator discovers the model(s) to refresh.

    - ``SELF``: the first positional arg is the target (standard instance methods).
    - ``RESULT``: the method's return value is the target (or an iterable of targets).
    - ``MANUAL``: the method body calls ``register_action_target`` itself.
    """

    SELF = "self"
    RESULT = "result"
    MANUAL = "manual"


ActionContextEntryType = tuple["AtomicRedisModel", "ActionGroup", bool]
_action_context: contextvars.ContextVar[Optional[list[ActionContextEntryType]]] = (
    contextvars.ContextVar("rapyer_action_context", default=None)
)


def register_action_target(
    model: "AtomicRedisModel",
    action: "ActionGroup",
    *,
    initial: bool = False,
):
    """
    Register a model for TTL refresh at the outer decorator boundary.
    """
    ctx = _action_context.get()
    if ctx is None:
        return
    ctx.append((model, action, initial))


def registerable_types() -> tuple:
    """Types the wrapper recognizes as TTL-refresh targets (lazy to avoid circular imports)."""
    from rapyer.base import AtomicRedisModel
    from rapyer.types.base import BaseRedisType

    return AtomicRedisModel, BaseRedisType


def register_from_result(result, action: "ActionGroup", *, initial: bool = False):
    """RESULT-mode helper: push returned model or iterable-of-models into the context."""
    targetable = registerable_types()

    if isinstance(result, targetable):
        register_action_target(result, action, initial=initial)
    elif isinstance(result, (list, tuple)):
        for item in result:
            if isinstance(item, targetable):
                register_action_target(item, action, initial=initial)


async def flush_action_targets(targets: list[ActionContextEntryType]):
    """Dedup registered targets by model.key and refresh TTL once per unique key."""
    merged: dict[str, tuple["AtomicRedisModel", ActionGroup, bool]] = {}
    for model, action, initial in targets:
        existing = merged.get(model.key)
        if existing is None:
            merged[model.key] = (model, action, initial)
        else:
            # OR-merge action groups and `initial` flag. An `initial=True`
            # signal from any registrant upgrades the merged entry so that
            # first-time TTL still gets set even if no registrant triggers
            # a normal refresh (harmless for existing TTLs — `nx=True`).
            merged[model.key] = (
                existing[0],
                existing[1] | action,
                existing[2] or initial,
            )

    for model, action, initial in merged.values():
        await model.refresh_ttl_if_needed(action=action, initial=initial)


def mark_actions(
    *groups: ActionGroup,
    target: TargetSource = TargetSource.SELF,
    initial: bool = False,
):
    """Tag a method with action groups for TTL refresh.

    - For async methods, wraps the method so that, at the outermost decorator
      boundary, TTL is refreshed for every model registered into the action
      context during the call. Nested decorated calls only contribute targets;
      they do not flush.
    - For sync methods, only tags the method with ``ACTION_GROUPS_ATTR``;
      TTL refresh is deferred to pipeline-exit via ``should_refresh()``.

    ``target`` controls which models the wrapper auto-registers

    ``initial=True`` marks the method as one that creates a model (e.g. ``asave``,
    ``ainsert``). Auto-registered targets will request "set TTL only if absent"
    semantics (EXPIRE NX), so that even with ``refresh_ttl=False`` the TTL is
    still established on first save.
    """
    combined = ActionGroup(0)
    for g in groups:
        combined |= g

    def decorator(method):
        setattr(method, ACTION_GROUPS_ATTR, combined)

        if not inspect.iscoroutinefunction(method):
            return method

        @functools.wraps(method)
        async def wrapper(*args, **kwargs):
            is_outer = _action_context.get() is None
            token = None
            targets: Optional[list[ActionContextEntryType]] = None
            if is_outer:
                targets = []
                token = _action_context.set(targets)
            try:
                if target is TargetSource.SELF and args:
                    first = args[0]
                    if isinstance(first, registerable_types()):
                        register_action_target(first, combined, initial=initial)
                result = await method(*args, **kwargs)
                if target is TargetSource.RESULT:
                    register_from_result(result, combined, initial=initial)
            finally:
                if is_outer:
                    _action_context.reset(token)
            if is_outer and targets is not None:
                await flush_action_targets(targets)
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
