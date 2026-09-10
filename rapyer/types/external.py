from abc import ABC
from typing import Annotated, Any, Generic, Optional, TypeVar, get_args, get_origin

from rapyer.types.base import BaseRedisType
from rapyer.types.traits import FieldTrait
from rapyer.utils.pythonic import resolve_generic_args, safe_issubclass

ConfigT = TypeVar("ConfigT")


class ExternalFieldType(BaseRedisType, ABC, Generic[ConfigT]):
    """
    Base for field types whose data lives outside the parent's JSON document.
    """

    @classmethod
    def config_type(cls) -> Optional[type]:
        """The config annotation this type reads, from its generic parameter."""
        for klass in cls.__mro__:
            for base in klass.__dict__.get("__orig_bases__", ()):
                # Only a level that re-declares ConfigT carries the config in args[0].
                if getattr(get_origin(base), "__parameters__", ())[:1] != (ConfigT,):
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
    def config_readers(cls, annotation) -> tuple:
        """This type if it declares a config class, plus whatever its elements declare."""
        mine = (cls,) if cls.config_type() is not None else ()
        return mine + super().config_readers(annotation)

    @classmethod
    def resolve_configs(cls, annotation) -> tuple:
        """This type's own config, then whatever its elements declare."""
        own = cls.extract_config(annotation)
        mine = (own,) if own is not None else ()
        return mine + super().resolve_configs(annotation)

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
