import abc
from typing import TYPE_CHECKING, Any, get_args, get_origin

from rapyer.types.base import BaseRedisType
from rapyer.utils.pythonic import safe_issubclass

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel


class RelationalFieldType(BaseRedisType, abc.ABC):
    """
    Base for field types that reference another ``AtomicRedisModel`` by key.

    Unlike ``SpecialFieldType``, the on-disk representation is **inline** in the
    parent's JSON (the target's Redis key as a string); the value lives at a
    separate key but is fetched on demand rather than stored separately.
    """

    # The generic argument as captured at class-build time: a model class, a
    # forward-ref string, or a metaclass-converted per-field subclass.
    _target_type_hint: Any = None
    # The canonical, registered target model. Populated once at init by
    # ``resolve_relational_targets`` and read by ``afetch`` — never resolved
    # per fetch.
    _relational_target: "type[AtomicRedisModel] | None" = None

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
        """Return the hydrated target instance.

        Raises ``NotResolvedError`` when called before ``afetch``.
        """

    @abc.abstractmethod
    async def afetch(self) -> Any:
        """Resolve the target from Redis and cache it in-place."""


def _resolve_target_model(target_hint: Any) -> "type[AtomicRedisModel] | None":
    """
    Map a generic argument to the canonical, registered top-level model.

    Resolves by ``__name__`` against ``REDIS_MODELS`` so a forward-ref string or
    the metaclass-converted per-field subclass both collapse to the registered,
    detached model. Returns ``None`` for an unbound ``TypeVar``.
    """
    # TODO: this name-normalization exists only because the metaclass converts a
    # ForeignKey's target into a dynamic per-field subclass. Once reference
    # targets are kept as static types, this can be removed (or reduced to a thin
    # forward-ref-string fallback).
    # https://github.com/imaginary-cherry/rapyer/issues/247
    from rapyer.base import REDIS_MODELS

    name = (
        target_hint
        if isinstance(target_hint, str)
        else getattr(target_hint, "__name__", None)
    )
    if name is None:
        return None
    for model in REDIS_MODELS:
        if model.__name__ == name:
            return model
    if isinstance(target_hint, str):
        raise NameError(
            f"ForeignKey target {target_hint!r} is not a registered rapyer model"
        )
    return None


def _iter_relational_types(annotation: Any):
    """Yield every ``RelationalFieldType`` subclass reachable in an annotation."""
    origin = get_origin(annotation) or annotation
    if safe_issubclass(origin, RelationalFieldType):
        yield origin
        return
    for arg in get_args(annotation):
        yield from _iter_relational_types(arg)


def resolve_relational_targets(models) -> None:
    """
    Resolve and cache every relational field's target model, once.

    Called at the init stage (``init_rapyer``) after all models are registered,
    so forward references and self-references all resolve. Only the fields the
    metaclass already flagged (``_relational_field_names`` + ``_contain_fk``) are
    visited — no recursive scan of every field — and each target is cached on its
    field type, so ``afetch`` never hits the registry.
    """
    for model in models:
        for fname in model._relational_field_names | model._contain_fk:
            annotation = model.model_fields[fname].annotation
            for rel_type in _iter_relational_types(annotation):
                rel_type._relational_target = _resolve_target_model(
                    rel_type._target_type_hint
                )
