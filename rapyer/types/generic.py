import abc
import logging
from abc import ABC
from typing import Any, Generic, TypeVar, get_origin

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from pydantic_core.core_schema import CoreSchema, SerializationInfo, ValidationInfo

from rapyer.errors import CantSerializeRedisValueError
from rapyer.types.base import RedisType
from rapyer.types.special import SpecialFieldType
from rapyer.utils.pythonic import resolve_generic_args, safe_issubclass

logger = logging.getLogger("rapyer")

SKIP_SENTINEL = object()

T = TypeVar("T")


class GenericRedisType(RedisType, Generic[T], ABC):
    safe_load: bool = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, val in self.iterate_items():
            self.init_redis_field(key, val)

    @classmethod
    def find_inner_type(cls, type_):
        args = resolve_generic_args(type_)
        return args[0] if args else Any

    @classmethod
    def contains_sf_field(cls) -> bool:
        inner = cls.find_inner_type(cls)
        if inner is Any:
            return False
        if safe_issubclass(inner, SpecialFieldType):
            return True
        contains = getattr(inner, "contains_sf_field", None)
        if contains is None:
            return False
        return contains()

    @classmethod
    def contains_fk_field(cls) -> bool:
        inner = cls.find_inner_type(cls)
        if inner is Any:
            return False

        from rapyer.types.relational import RelationalFieldType

        # inner may be a parameterized alias (e.g. ForeignKey[Author]); reduce
        # it to its origin class before the subclass check.
        inner = get_origin(inner) or inner
        if safe_issubclass(inner, RelationalFieldType):
            return True
        contains = getattr(inner, "contains_fk_field", None)
        if contains is None:
            return False
        return contains()

    @classmethod
    @abc.abstractmethod
    def build_typed_original(cls, source_args):
        pass  # pragma: no cover

    @classmethod
    def try_deserialize_item(cls, item, identifier):
        try:
            return cls.deserialize_unknown(item)
        except Exception as e:
            if cls.safe_load:
                logger.warning(
                    "SafeLoad: Failed to deserialize item at '%s'.", identifier
                )
                return SKIP_SENTINEL
            raise CantSerializeRedisValueError() from e

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
            # Normal serialization for concrete types — preserve inner type args
            args = resolve_generic_args(source_type)
            inner_type = cls.build_typed_original(args)
            return core_schema.no_info_after_validator_function(
                cls, handler(inner_type)
            )
