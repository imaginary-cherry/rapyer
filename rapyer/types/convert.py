from typing import Any, get_origin

from pydantic import BaseModel, PrivateAttr, TypeAdapter

from rapyer.types.base import RedisType
from rapyer.utils.annotation import TypeConverter, DYNAMIC_CLASS_DOC
from rapyer.utils.pythonic import safe_issubclass


class RedisConverter(TypeConverter):
    def __init__(self, supported_types: dict[type, type], field_name: str):
        self.supported_types = supported_types
        self.field_name = field_name

    def is_redis_type(self, type_to_check: type) -> bool:
        origin = get_origin(type_to_check) or type_to_check
        if safe_issubclass(origin, RedisType):
            return True
        from rapyer.base import AtomicRedisModel

        return safe_issubclass(origin, AtomicRedisModel)

    def is_type_support(self, type_to_check: type) -> bool:
        if safe_issubclass(type_to_check, BaseModel):
            return True
        if safe_issubclass(type_to_check, RedisType):
            return True
        return type_to_check in self.supported_types

    def convert_flat_type(self, type_to_convert: type) -> type:
        from rapyer.base import AtomicRedisModel

        if safe_issubclass(type_to_convert, AtomicRedisModel):
            return type(
                type_to_convert.__name__,
                (type_to_convert,),
                dict(
                    _field_name=PrivateAttr(default=self.field_name),
                    __doc__=DYNAMIC_CLASS_DOC,
                ),
            )
        if safe_issubclass(type_to_convert, BaseModel):
            origin: type[BaseModel]
            return type(
                f"Redis{type_to_convert.__name__}",
                (AtomicRedisModel, type_to_convert),
                dict(
                    _field_name=PrivateAttr(default=self.field_name),
                    __doc__=DYNAMIC_CLASS_DOC,
                ),
            )
        if safe_issubclass(type_to_convert, RedisType):
            redis_type = type_to_convert
            original_type = type_to_convert.original_type
        else:
            redis_type = self.supported_types[type_to_convert]
            original_type = type_to_convert

        new_type = type(
            redis_type.__name__,
            (redis_type,),
            dict(
                field_name=self.field_name,
                original_type=original_type,
                __doc__=DYNAMIC_CLASS_DOC,
            ),
        )

        new_type._adapter = TypeAdapter(new_type)
        return new_type

    def covert_generic_type(
        self, type_to_covert: type, generic_values: tuple[type]
    ) -> type:
        if safe_issubclass(type_to_covert, RedisType):
            redis_type = type_to_covert
            original_type = type_to_covert.original_type
        else:
            redis_type = self.supported_types[type_to_covert]
            original_type = type_to_covert
            original_type = original_type[generic_values]

        new_type = type(
            redis_type.__name__,
            (redis_type,),
            dict(
                field_name=self.field_name,
                original_type=original_type,
                __doc__=DYNAMIC_CLASS_DOC,
            ),
        )
        adapter_type = new_type[generic_values]

        if issubclass(redis_type, RedisType):
            new_type._adapter = TypeAdapter(adapter_type)
        return new_type[generic_values]
