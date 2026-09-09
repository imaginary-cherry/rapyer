import abc
import dataclasses
from enum import Flag, auto
from typing import Annotated, Any, Generic, Optional, TypeVar, get_args, get_origin

from rapyer.types.base import BaseRedisType
from rapyer.utils.pythonic import resolve_generic_args, safe_issubclass

ConfigT = TypeVar("ConfigT")


class FieldTrait(Flag):
    """What a field type contributes to a walk."""

    # INDEXED is deliberately absent — add it only once a walk needs it.

    # Owns a Redis key that dies with the parent; the delete and TTL sweeps collect it.
    # RedisSet: _all_keys_for_key adds __rapyer_special__:{key}:tags to the doc key.
    OWNS_KEYS = auto()
    # Never serialized into the parent JSON, so the document dump excludes the field.
    # RedisSet: build_redis_dump_exclude drops "tags" before JSON.SET writes the doc.
    EXCLUDED_FROM_DOC = auto()
    # Contributes a slot to the load pipeline; lazily-fetched types declare none.
    # RedisSet has it, RedisPriorityQueue does not — apeek/aitems fetch on demand.
    LOADS_WITH_DOC = auto()
    # The live instance must be visited to save it, not just its class-level facts.
    # asave walks _iter_special_fields and calls asave_special() on each RedisSet.
    HOLDS_LIVE_STATE = auto()
    # Names a separate document with its own key and TTL; cascade decides the hop.
    # ForeignKey only: the planner's FK-edge walk turns each into a CascadeEdge.
    REFERENCES_ROOT = auto()


@dataclasses.dataclass(frozen=True)
class ExternalFieldSpec(Generic[ConfigT]):
    """
    One external field's class-level facts, resolved at class-build time.
    """

    name: str
    field_type: type["ExternalFieldType[ConfigT]"]
    config: Optional[ConfigT] = None


class ExternalFieldType(BaseRedisType, abc.ABC, Generic[ConfigT]):
    """
    Base for field types whose data lives outside the parent's JSON document.
    """

    @classmethod
    def config_type(cls) -> Optional[type]:
        """The config annotation this type reads, from its generic parameter."""
        # Lazy import: a module-level import here would cycle (both subclass this module).
        from rapyer.types.relational import RelationalFieldType
        from rapyer.types.special import SpecialFieldType

        config_bases = (ExternalFieldType, SpecialFieldType, RelationalFieldType)
        for klass in cls.__mro__:
            for base in klass.__dict__.get("__orig_bases__", ()):
                if get_origin(base) not in config_bases:
                    continue
                args = get_args(base)
                if args and not isinstance(args[0], TypeVar):
                    # X[None] normalizes to NoneType inside the subscript; report as None.
                    return None if args[0] is type(None) else args[0]
        return None

    @classmethod
    def extract_config(cls, annotation) -> Optional[ConfigT]:
        """Pull this type's config out of a field annotation, or None."""
        config_cls = cls.config_type()
        if config_cls is None or get_origin(annotation) is not Annotated:
            return None
        for metadata in get_args(annotation)[1:]:
            if isinstance(metadata, config_cls):
                return metadata
        return None

    @classmethod
    def owns_serialization(cls) -> bool:
        """Whether the type serializes itself, so no pickle serializer is installed."""
        return True

    @classmethod
    def traits(cls) -> FieldTrait:
        """What this type contributes to a walk."""
        return FieldTrait(0)

    @classmethod
    def inner_traits(cls) -> FieldTrait:
        """What is reachable through this type's generic element, e.g. RedisSet[ForeignKey[X]]."""
        args = resolve_generic_args(cls)
        inner = args[0] if args else Any
        if inner is Any:
            return FieldTrait(0)
        inner = get_origin(inner) or inner
        if not safe_issubclass(inner, BaseRedisType):
            return FieldTrait(0)
        return inner.traits() | inner.inner_traits()

    @classmethod
    def owned_redis_keys(cls, model_key: str, field_path: str) -> list[str]:
        """Keys that belong to the parent and die with it."""
        return []
