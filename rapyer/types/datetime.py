from datetime import datetime
from typing import TYPE_CHECKING

from pydantic_core import core_schema
from pydantic_core.core_schema import ValidationInfo, SerializationInfo
from redis.commands.search.field import NumericField

from rapyer.types.base import RedisType, REDIS_DUMP_FLAG_NAME


class RedisDatetime(datetime, RedisType):
    original_type = datetime

    def __new__(cls, value, *args, **kwargs):
        if isinstance(value, datetime):
            # Support init from a datetime, preserving microseconds and timezone
            return datetime.__new__(
                cls,
                value.year,
                value.month,
                value.day,
                value.hour,
                value.minute,
                value.second,
                value.microsecond,
                value.tzinfo,
            )
        else:
            return datetime.__new__(cls, value, *args, **kwargs)

    def clone(self):
        return datetime.fromtimestamp(self.timestamp())


class RedisDatetimeTimestamp(RedisDatetime):

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.with_info_before_validator_function(
                cls._validate_timestamp, handler(cls.original_type)
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._serialize_timestamp,
                return_schema=core_schema.float_schema(),
                info_arg=True,
            ),
        )

    @classmethod
    def _validate_timestamp(cls, value, info: ValidationInfo):
        ctx = info.context or {}
        is_redis_data = ctx.get(REDIS_DUMP_FLAG_NAME)

        if isinstance(value, (int, float)) and is_redis_data:
            return datetime.fromtimestamp(value)
        return value

    @classmethod
    def _serialize_timestamp(cls, value, info: SerializationInfo):
        ctx = info.context or {}
        is_redis_data = ctx.get(REDIS_DUMP_FLAG_NAME)

        if is_redis_data:
            return value.timestamp()
        return value

    @classmethod
    def redis_schema(cls, field_name: str):
        return NumericField(f"$.{field_name}", as_name=field_name)


if TYPE_CHECKING:
    RedisDatetime = RedisDatetime | datetime  # pragma: no cover
    RedisDatetimeTimestamp = RedisDatetimeTimestamp | datetime  # pragma: no cover
