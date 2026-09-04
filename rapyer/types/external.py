import abc
from typing import Generic, Optional, TypeVar

from rapyer.types.base import BaseRedisType

ConfigT = TypeVar("ConfigT")


class ExternalFieldType(BaseRedisType, abc.ABC, Generic[ConfigT]):
    """
    Base for field types whose data lives outside the parent's JSON document.
    """

    @classmethod
    def config_type(cls) -> Optional[type]:
        """The config annotation this type reads, from its generic parameter."""
        return None

    @classmethod
    def extract_config(cls, annotation) -> Optional[ConfigT]:
        """Pull this type's config out of a field annotation, or None."""
        return None

    @classmethod
    def owns_serialization(cls) -> bool:
        """Whether the type serializes itself, so no pickle serializer is installed."""
        return True

    @classmethod
    def owned_redis_keys(cls, model_key: str, field_path: str) -> list[str]:
        """Keys that belong to the parent and die with it."""
        return []
