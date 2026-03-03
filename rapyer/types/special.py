import abc
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from rapyer.types.base import BaseRedisType


class SpecialFieldType(BaseRedisType, abc.ABC):
    """Base for field types stored separately from the model's JSON dump.

    Special field types are saved under a separate Redis key derived from
    the parent model's key and the field path. Each subclass defines its
    own storage mechanism (e.g., Sorted Set, Stream, etc.).

    Methods use ``self.client`` which is pipeline-aware: when called inside
    an ``ensure_pipeline()`` context, operations are automatically batched.
    """

    @property
    def special_key(self) -> str:
        """Redis key for this field's separate data structure.

        Format: ``{model_key}:{field_name_without_dot}``
        e.g., ``MyModel:abc123:tasks``
        """
        clean_name = self.field_name.lstrip(".")
        return f"{self.key}:{clean_name}"

    @abc.abstractmethod
    async def asave_special(self) -> None:
        """Save this field's data to its separate Redis structure.

        Uses ``self.client`` which is pipeline-aware.
        """

    @abc.abstractmethod
    async def adelete_special(self) -> None:
        """Delete this field's separate Redis data.

        Uses ``self.client`` which is pipeline-aware.
        """

    def clone(self):
        return self.__class__()

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(
            lambda v: v if isinstance(v, cls) else cls(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: None,
            ),
        )
