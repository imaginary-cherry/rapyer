import abc
from types import UnionType
from typing import (
    TYPE_CHECKING,
    Any,
    ForwardRef,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

from rapyer.types.external import ExternalFieldType, FieldTrait
from rapyer.utils.pythonic import resolve_generic_args, safe_issubclass

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel

ConfigT = TypeVar("ConfigT")


class RelationalFieldType(ExternalFieldType[ConfigT], abc.ABC):
    """
    Base for field types that reference another ``AtomicRedisModel`` by key.

    Unlike ``SpecialFieldType``, the on-disk representation is **inline** in the
    parent's JSON (the target's Redis key as a string); the value lives at a
    separate key but is fetched on demand rather than stored separately.
    """

    @property
    def _relational_target(self) -> "type[AtomicRedisModel] | None":
        """Find the refernced class"""
        orig = getattr(self, "__orig_class__", None)
        args = get_args(orig) if orig is not None else ()
        return args[0] if args else None

    @property
    @abc.abstractmethod
    def target_key(self) -> str | None:
        """Redis key of the referenced model, or ``None`` if unset."""

    @property
    @abc.abstractmethod
    def is_resolved(self) -> bool:
        """Whether the target has been hydrated into memory."""

    @property
    @abc.abstractmethod
    def value(self) -> "AtomicRedisModel":
        """
        Return the hydrated target instance.

        Raises ``NotResolvedError`` when called before ``afetch``.
        """

    @abc.abstractmethod
    async def afetch(self) -> Any:
        """Resolve the target from Redis and cache it in-place."""

    @classmethod
    def relational_targets(
        cls, annotation: Any, models: "list[type[AtomicRedisModel]]"
    ) -> "list[type[AtomicRedisModel]]":
        """
        Every model class an annotation of this type can point to, empty if
        the annotation is not FK-shaped anywhere within it.
        """
        # Lazy import: rapyer.utils.annotation imports RelationalFieldType at module level.
        from rapyer.utils.annotation import strip_optional

        stripped = strip_optional(annotation)
        origin = get_origin(stripped) or stripped
        if safe_issubclass(origin, RelationalFieldType):
            args = resolve_generic_args(stripped)
            target = args[0] if args else None
            if target is None:
                return []
            # Reference[A | B] contributes one candidate per union member.
            if get_origin(target) in (Union, UnionType):
                members = get_args(target)
            else:
                members = (target,)
            candidates: "list[type[AtomicRedisModel]]" = []
            for member in members:
                resolved = (
                    _resolve_forward_ref(member, models)
                    if isinstance(member, ForwardRef)
                    else member
                )
                if resolved is None:
                    continue
                for candidate in _expand_candidates(resolved, models):
                    if candidate not in candidates:
                        candidates.append(candidate)
            return candidates
        accumulated: "list[type[AtomicRedisModel]]" = []
        for arg in resolve_generic_args(stripped):
            for candidate in cls.relational_targets(arg, models):
                if candidate not in accumulated:
                    accumulated.append(candidate)
        return accumulated


def _resolve_forward_ref(
    forward_ref: ForwardRef, models: "list[type[AtomicRedisModel]]" = ()
) -> Any | None:
    """Resolve a forward-ref FK target to its model class, or None."""
    # Lazy import avoids a cycle back into rapyer.base.
    from rapyer.base import REDIS_MODELS

    name = forward_ref.__forward_arg__
    # The caller's collection wins: it may hold a target the global registry skipped,
    # such as a generic origin or a model opting out with Meta.init_with_rapyer=False.
    for model in (*models, *REDIS_MODELS):
        if model.__name__ == name:
            return model
    return None


def _expand_candidates(
    target_cls: Any, models: "list[type[AtomicRedisModel]]"
) -> "list[type[AtomicRedisModel]]":
    """Return target_cls together with its registered subclasses, in declaration order."""
    return [m for m in models if safe_issubclass(m, target_cls)]


def resolve_relational_targets(models) -> None:
    """
    Rebuild every model that holds a reference so pydantic resolves forward-ref
    targets to real classes.

    A forward reference to a model defined later stays unresolved in the field
    annotation otherwise. Each ``ForeignKey`` stamps its resolved target onto the
    instance at validation time, so this only needs to force that rebuild.
    """
    for model in models:
        if model.reachable_fields_w_traits() & FieldTrait.REFERENCES_ROOT:
            model.model_rebuild(force=True)
