import abc
import dataclasses
from typing import Annotated, Any, Generic, Optional, TypeVar, get_args, get_origin

from rapyer.types.base import BaseRedisType
from rapyer.types.traits import FieldTrait
from rapyer.utils.pythonic import resolve_generic_args, safe_issubclass

ConfigT = TypeVar("ConfigT")


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
    def reachable_fields_w_traits(cls) -> FieldTrait:
        """What is reachable through this type's generic element, e.g. RedisSet[ForeignKey[X]]."""
        args = resolve_generic_args(cls)
        inner = args[0] if args else Any
        if inner is Any:
            return FieldTrait(0)
        inner = get_origin(inner) or inner
        if not safe_issubclass(inner, BaseRedisType):
            return FieldTrait(0)
        return inner.traits() | inner.reachable_fields_w_traits()

    @classmethod
    def owned_redis_keys(cls, model_key: str, field_path: str) -> list[str]:
        """Keys that belong to the parent and die with it."""
        return []
