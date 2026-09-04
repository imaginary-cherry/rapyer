import abc
from typing import TYPE_CHECKING, Any, TypeVar, get_args

from rapyer.types.external import ExternalFieldType

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


def resolve_relational_targets(models) -> None:
    """
    Rebuild every model that holds a reference so pydantic resolves forward-ref
    targets to real classes.

    A forward reference to a model defined later stays unresolved in the field
    annotation otherwise. Each ``ForeignKey`` stamps its resolved target onto the
    instance at validation time, so this only needs to force that rebuild.
    """
    for model in models:
        if model.contains_fk_field():
            model.model_rebuild(force=True)
