import abc
import base64
import pickle
from abc import ABC
from typing import get_args, Any, TypeVar, Generic

from pydantic import GetCoreSchemaHandler, TypeAdapter
from pydantic_core import core_schema
from pydantic_core.core_schema import ValidationInfo, CoreSchema, SerializationInfo
from redis.commands.search.field import TextField
from typing_extensions import deprecated

from rapyer.context import _context_var
from rapyer.typing_support import Self
from rapyer.utils.redis import refresh_ttl_if_needed

REDIS_DUMP_FLAG_NAME = "__rapyer_dumped__"


class RedisType(ABC):
    original_type: type = None
    field_name: str = None
    _adapter: TypeAdapter = None

    @property
    def redis(self):
        return self._base_model_link.Meta.redis

    @property
    def key(self):
        return self._base_model_link.key

    @property
    def Meta(self):
        return self._base_model_link.Meta

    @property
    def field_path(self) -> str:
        base_path = self._base_model_link.field_path
        return f"{base_path}{self.field_name}"

    @property
    def pipeline(self):
        return _context_var.get()

    @property
    def client(self):
        return _context_var.get() or self.redis

    @property
    def json_path(self):
        return f"${self.field_path}"

    def __init__(self, *args, **kwargs):
        # Note: This should be overridden in the base class AtomicRedisModel, it would allow me to get access to a redis key
        self._base_model_link = None

    def init_redis_field(self, key, val):
        if hasattr(val, "_base_model_link"):
            val._base_model_link = self
            val.field_name = key

    def sub_field_path(self, key: str):
        return f"{self.field_path}.{key}"

    def json_field_path(self, field_name: str):
        return f"${self.sub_field_path(field_name)}"

    @deprecated(
        f"save function is deprecated and will become sync function in rapyer 1.2.0, use asave() instead"
    )
    async def save(self):
        return await self.asave()  # pragma: no cover

    async def asave(self) -> Self:
        model_dump = self._adapter.dump_python(
            self, mode="json", context={REDIS_DUMP_FLAG_NAME: True}
        )
        await self.client.json().set(self.key, self.json_path, model_dump)
        if self.Meta.ttl is not None:
            nx = not self.Meta.refresh_ttl
            await self.client.expire(self.key, self.Meta.ttl, nx=nx)
        return self

    @deprecated(
        "load function is deprecated and will be removed in rapyer 1.2.0, use aload() instead"
    )
    async def load(self):
        return await self.aload()  # pragma: no cover

    async def aload(self):
        redis_value = await self.client.json().get(self.key, self.field_path)
        if redis_value is None:
            return None
        result = self._adapter.validate_python(
            redis_value, context={REDIS_DUMP_FLAG_NAME: True}
        )
        await refresh_ttl_if_needed(
            self.client, self.key, self.Meta.ttl, self.Meta.refresh_ttl
        )
        return result

    @abc.abstractmethod
    def clone(self):
        pass  # pragma: no cover

    @classmethod
    def redis_schema(cls, field_name: str):
        return TextField(f"$.{field_name}", as_name=field_name)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls, handler(cls.original_type)
        )

    @staticmethod
    def serialize_unknown(value: Any):
        return base64.b64encode(pickle.dumps(value)).decode("utf-8")

    @staticmethod
    def deserialize_unknown(value: str):
        return pickle.loads(base64.b64decode(value))


T = TypeVar("T")


class GenericRedisType(RedisType, Generic[T], ABC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, val in self.iterate_items():
            self.init_redis_field(key, val)

    @classmethod
    def find_inner_type(cls, type_):
        args = get_args(type_)
        return args[0] if args else Any

    @abc.abstractmethod
    def iterate_items(self):
        pass  # pragma: no cover

    @classmethod
    @abc.abstractmethod
    def full_serializer(cls, value, info: SerializationInfo):
        pass  # pragma: no cover

    @classmethod
    @abc.abstractmethod
    def full_deserializer(cls, value, info: ValidationInfo):
        pass  # pragma: no cover

    @classmethod
    @abc.abstractmethod
    def schema_for_unknown(cls):
        pass  # pragma: no cover

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        # Extract the generic type argument T from source_type
        element_type = cls.find_inner_type(source_type)
        from rapyer.types.convert import RedisConverter

        checker = RedisConverter({}, "")
        should_pickle = not checker.is_redis_type(element_type)

        if should_pickle:
            # Build schema with both validator and serializer
            python_schema = core_schema.with_info_before_validator_function(
                cls.full_deserializer, handler(cls.original_type)
            )

            return core_schema.with_info_after_validator_function(
                lambda v, info: cls(v),
                python_schema,
                serialization=core_schema.plain_serializer_function_ser_schema(
                    cls.full_serializer,
                    info_arg=True,
                    return_schema=cls.schema_for_unknown(),
                ),
            )
        else:
            # Normal serialization for concrete types
            return core_schema.no_info_after_validator_function(
                cls, handler(cls.original_type)
            )
