import abc
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from rapyer.types.base import BaseRedisType

SPECIAL_FIELD_KEY_PREFIX = "__rapyer_special__"


class SpecialFieldType(BaseRedisType, abc.ABC):
    """Base for field types stored separately from the model's JSON dump.

    Special field types are saved under a separate Redis key derived from
    the parent model's key and the field path. Each subclass defines its
    own storage mechanism (e.g., Sorted Set, Stream, etc.).

    Methods use ``self.client`` which is pipeline-aware: when called inside
    an ``ensure_pipeline()`` context, operations are automatically batched.
    """

    @classmethod
    def special_field_key(cls, model_key: str, field_path: str) -> str:
        path = field_path
        clean_name = path.lstrip(".")
        return f"{SPECIAL_FIELD_KEY_PREFIX}:{model_key}:{clean_name}"

    @property
    def special_key(self) -> str:
        """Redis key for this field's separate data structure.

        Format: ``__rapyer_special__:{model_key}:{dotted_field_path}``
        e.g., ``__rapyer_special__:MyModel:abc123:tasks`` for a top-level field,
        ``__rapyer_special__:MyModel:abc123:inner.tasks`` for a nested one.
        """
        return self.special_field_key(self.key, self.field_path)

    @abc.abstractmethod
    async def asave_special(self):
        """Save this field's data to its separate Redis structure.

        Uses ``self.client`` which is pipeline-aware.
        """

    @abc.abstractmethod
    async def adelete_special(self):
        """Delete this field's separate Redis data.

        Uses ``self.client`` which is pipeline-aware.
        """

    @abc.abstractmethod
    async def aduplicate_special(self, target_special_key: str):
        """Copy this field's data to a new key for a duplicated model.

        The *read* must use ``self.redis`` (direct client) so the data is
        available immediately; the *write* should use ``self.client`` so it
        participates in any active pipeline.
        """

    def lua_save_commands(self) -> list[list]:
        """Return [[CMD, arg1, ...], ...] persisting this field's data.

        Data-form mirror of ``asave_special`` for use inside a single Lua
        script (e.g. ``aget_or_create``). The script ``unpack``s each entry
        into ``redis.call``.
        """
        raise NotImplementedError

    def lua_load_commands(self) -> list[list]:
        """Return [[CMD, arg1, ...], ...] reading this field's data.

        Data-form mirror of ``queue_special_loads_in_pipeline``.
        """
        raise NotImplementedError

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
