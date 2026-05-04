from __future__ import annotations

import contextvars
import enum
import functools
import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Literal, Optional

from rapyer.context import _context_pipe, ensure_pipeline

if TYPE_CHECKING:
    from rapyer import AtomicRedisModel
    from rapyer.config import RedisConfig


ACTION_GROUPS_ATTR = "_action_groups"
MARK_ACTION_PARAMS_ATTR = "_mark_action_params"
ACTION_WRAPPER_SENTINEL = "_rapyer_action_wrapper"


@dataclass(frozen=True, slots=True)
class MarkActionParams:
    """Params recorded by ``mark_actions(version="v2")`` for later install-time use."""

    combined: "ActionGroup"
    target: "TargetSource"
    initial: bool
    ignore_refresh: bool


class ActionGroup(enum.Flag):
    """Categories of operations that can trigger TTL refresh.

    - ``READ``: reading any value from Redis (field-level reads, contains-checks, etc.).
    - ``FETCH``: extracting a full model from Redis (``aget``, ``afind``, ``afind_one``).
    - ``UPDATE``: modifying existing data.
    - ``APPEND``: adding new items to a collection.
    - ``DELETE``: removing an entire model/key from Redis (``adelete``, ``adelete_many``).
    - ``ERASE``: removing item(s) from a collection while keeping the model (``apop``,
      ``apopitem``, ``adel_item``, ``aremove``, ``aclear``).
    - ``ARITHMETIC``: in-place numeric operations.
    """

    READ = enum.auto()
    FETCH = enum.auto()
    CREATE = enum.auto()
    UPDATE = enum.auto()
    APPEND = enum.auto()
    DELETE = enum.auto()
    ERASE = enum.auto()
    ARITHMETIC = enum.auto()

    @classmethod
    def all(cls, *, for_ttl: bool = False) -> "ActionGroup":
        result = cls(0)
        for member in cls:
            if for_ttl and member is cls.DELETE:
                continue
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


def register_from_result(result, action: "ActionGroup", *, initial: bool = False):
    if isinstance(result, (list, tuple)):
        for item in result:
            register_action_target(item, action, initial=initial)
    else:
        register_action_target(result, action, initial=initial)


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

    if not targets:
        return
    atomic_model = targets[0][0]

    async with ensure_pipeline(atomic_model.Meta):
        for model, action, initial in merged.values():
            await model.refresh_ttl_if_needed(
                can_use_pipeline=True, action=action, initial=initial
            )


def _build_action_wrapper(
    method,
    combined: "ActionGroup",
    target: "TargetSource",
    initial: bool,
):
    """Build the async wrapper that opens an action context and flushes on exit."""

    if target is TargetSource.SELF:

        @functools.wraps(method)
        async def wrapper(*args, **kwargs):
            is_outer = _action_context.get() is None
            token = None
            targets: Optional[list[ActionContextEntryType]] = None
            if is_outer:
                targets = []
                token = _action_context.set(targets)
            try:
                if args:
                    first = args[0]
                    register_action_target(first, combined, initial=initial)
                result = await method(*args, **kwargs)
            finally:
                if is_outer:
                    _action_context.reset(token)
            if is_outer and targets is not None:
                await flush_action_targets(targets)
            return result

    elif target is TargetSource.RESULT:

        @functools.wraps(method)
        async def wrapper(*args, **kwargs):
            is_outer = _action_context.get() is None
            token = None
            targets: Optional[list[ActionContextEntryType]] = None
            if is_outer:
                targets = []
                token = _action_context.set(targets)
            try:
                result = await method(*args, **kwargs)
                register_from_result(result, combined, initial=initial)
            finally:
                if is_outer:
                    _action_context.reset(token)
            if is_outer and targets is not None:
                await flush_action_targets(targets)
            return result

    else:  # TargetSource.MANUAL

        @functools.wraps(method)
        async def wrapper(*args, **kwargs):
            is_outer = _action_context.get() is None
            token = None
            targets: Optional[list[ActionContextEntryType]] = None
            if is_outer:
                targets = []
                token = _action_context.set(targets)
            try:
                result = await method(*args, **kwargs)
            finally:
                if is_outer:
                    _action_context.reset(token)
            if is_outer and targets is not None:
                await flush_action_targets(targets)
            return result

    setattr(wrapper, ACTION_GROUPS_ATTR, combined)
    setattr(wrapper, ACTION_WRAPPER_SENTINEL, True)
    return wrapper


def mark_actions(
    *groups: ActionGroup,
    target: TargetSource = TargetSource.SELF,
    initial: bool = False,
    ignore_refresh: bool = False,
    version: Literal["v1", "v2"] = "v1",
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

    ``ignore_refresh=True`` skips wrapping entirely — the method is tagged with
    ``ACTION_GROUPS_ATTR`` for inspection/grouping, but no action context is
    opened and no TTL refresh is triggered (e.g. ``adelete``, ``aset_ttl``).

    ``version`` selects when the wrap/no-wrap decision happens:

    - ``"v1"`` (default): check whether we should refresh at runtime
    - ``"v2"``: Minimize runtime - adjust the code to run for only actions that need it.
    """
    combined = ActionGroup(0)
    for g in groups:
        combined |= g

    def decorator(method):
        setattr(method, ACTION_GROUPS_ATTR, combined)

        if version == "v2":
            setattr(
                method,
                MARK_ACTION_PARAMS_ATTR,
                MarkActionParams(combined, target, initial, ignore_refresh),
            )
            return method

        if not inspect.iscoroutinefunction(method) or ignore_refresh:
            return method

        return _build_action_wrapper(method, combined, target, initial)

    return decorator


def marks_redis_updated(method):
    """
    We mark when the field was already updated to prevent duplicated updates.
    This is usually helps in self assign field like model.int_field += 1
    where both __iadd__ of int and __setitem__ of atmoic model
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


def install_action_for_meta(func: Callable, meta: "RedisConfig"):
    params: Optional[MarkActionParams] = getattr(func, MARK_ACTION_PARAMS_ATTR, None)
    if params is None:
        return func
    # Peel back only past wrappers WE installed previously (e.g. parent class
    # install of the same method with a different meta). Other wrappers like
    # ``marks_redis_updated`` must stay in place so the call chain is preserved
    # — both for the wrap branch and the no-wrap branch.
    base_func = func
    while getattr(base_func, ACTION_WRAPPER_SENTINEL, False):
        base_func = base_func.__wrapped__
    is_async = inspect.iscoroutinefunction(base_func)
    should_refresh = (
        not params.ignore_refresh
        and is_async
        and should_refresh_for_action(meta, params.combined)
    )
    should_start_ttl = params.initial and meta.ttl and is_async
    if should_refresh or should_start_ttl:
        return _build_action_wrapper(
            base_func, params.combined, params.target, params.initial
        )
    return base_func


def install_marked_action_methods(cls: type, meta: Optional["RedisConfig"] = None):
    """Wrap methods that need ttl handling.

    When ``meta`` is omitted, falls back to ``cls.Meta`` (the AtomicRedisModel
    path). For BaseRedisType field subclasses, the owning model's meta is
    passed in explicitly because they don't carry their own ``Meta`` class.
    """
    if meta is None:
        meta = cls.Meta
    seen: set[str] = set()
    for klass in cls.__mro__:
        if klass is object:
            break
        for name, attr in vars(klass).items():
            if name in seen:
                continue
            seen.add(name)
            if isinstance(attr, classmethod):
                raw_func = attr.__func__
                rebuild = classmethod
            elif isinstance(attr, staticmethod):
                raw_func = attr.__func__
                rebuild = staticmethod
            elif inspect.isfunction(attr):
                raw_func = attr
                rebuild = None
            else:
                continue
            if not hasattr(raw_func, MARK_ACTION_PARAMS_ATTR):
                continue
            installed = install_action_for_meta(raw_func, meta)
            if rebuild is not None:
                installed = rebuild(installed)
            setattr(cls, name, installed)
