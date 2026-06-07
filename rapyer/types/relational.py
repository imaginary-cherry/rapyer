import abc
from typing import TYPE_CHECKING, Any

from rapyer.types.base import BaseRedisType

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel


class RelationalFieldType(BaseRedisType, abc.ABC):
    """
    Base for field types that reference another ``AtomicRedisModel`` by key.

    Unlike ``SpecialFieldType``, the on-disk representation is **inline** in the
    parent's JSON (the target's Redis key as a string); the value lives at a
    separate key but is fetched on demand rather than stored separately.
    """

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
