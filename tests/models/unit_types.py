from datetime import datetime

from pydantic import Field
from rapyer.base import AtomicRedisModel
from rapyer.types import RedisDatetimeTimestamp


# Unit test models for simple types
class SimpleStringModel(AtomicRedisModel):
    name: str = ""


class SimpleIntModel(AtomicRedisModel):
    count: int = 0


class SimpleFloatModel(AtomicRedisModel):
    value: float = 0.0


class SimpleBoolModel(AtomicRedisModel):
    flag: bool = False


class SimpleBytesModel(AtomicRedisModel):
    data: bytes = b""


class MultiTypeModel(AtomicRedisModel):
    name: str = ""
    count: int = 0
    flag: bool = False
    data: bytes = b""


# Unit test models for collection types
class SimpleIntDictModel(AtomicRedisModel):
    counts: dict[str, int] = Field(default_factory=dict)


class MixedCollectionModel(AtomicRedisModel):
    str_list: list[str] = Field(default_factory=list)
    int_list: list[int] = Field(default_factory=list)
    str_dict: dict[str, str] = Field(default_factory=dict)
    int_dict: dict[str, int] = Field(default_factory=dict)


# Models for various operations testing
class OperationsTestModel(AtomicRedisModel):
    str_field: str = "default"
    int_field: int = 0
    bool_field: bool = True
    list_field: list[str] = Field(default_factory=list)
    dict_field: dict[str, str] = Field(default_factory=dict)


# Generic test model for operations
class TestOperationsModel(AtomicRedisModel):
    name: str = "test"
    count: int = 0
    items: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


# Model with RedisDatetimeTimestamp for testing serialization
class DatetimeTimestampModel(AtomicRedisModel):
    created_at: RedisDatetimeTimestamp = Field(default_factory=datetime.now)
    updated_at: RedisDatetimeTimestamp = Field(default_factory=datetime.now)
