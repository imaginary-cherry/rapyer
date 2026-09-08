import abc
import dataclasses
import enum
from typing import Annotated, Generic, Optional, TypeVar, get_args, get_origin

from rapyer.types.base import BaseRedisType

ConfigT = TypeVar("ConfigT")


class Capability(enum.Flag):
    """What a field type contributes to a walk."""

    # INDEXED is deliberately absent — add it only once a walk needs it.
    OWNS_KEYS = enum.auto()
    EXCLUDED_FROM_DOC = enum.auto()
    PIPELINE_LOAD = enum.auto()
    INSTANCE_STATE = enum.auto()
    REFERENCES_ROOT = enum.auto()


@dataclasses.dataclass(frozen=True)
class ExternalFieldSpec(Generic[ConfigT]):
    """
    One external field's class-level facts, resolved at class-build time.
    """

    name: str
    field_type: type["ExternalFieldType[ConfigT]"]
    config: Optional[ConfigT] = None
    # Special and relational never co-occur, so one flag holds the kind.
    is_special: bool = False


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
    def capabilities(cls) -> Capability:
        """What this type contributes to a walk."""
        return Capability(0)

    @classmethod
    def owned_redis_keys(cls, model_key: str, field_path: str) -> list[str]:
        """Keys that belong to the parent and die with it."""
        return []
