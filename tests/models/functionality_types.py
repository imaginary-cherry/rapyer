from datetime import datetime
from enum import Enum
from typing import List

from pydantic import Field

from rapyer.base import AtomicRedisModel


class RichModel(AtomicRedisModel):
    name: str = ""
    age: int = 0
    tags: List[str] = Field(default_factory=list)
    active: bool = True
    date1: str = ""


class LockTestModel(AtomicRedisModel):
    name: str = "test"
    counter: int = 0
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class LockUpdateTestModel(AtomicRedisModel):
    name: str = ""
    value: int = 0
    tags: List[str] = Field(default_factory=list)


class LockSaveTestModel(AtomicRedisModel):
    name: str = ""
    age: int = 0
    tags: List[str] = Field(default_factory=list)
    active: bool = True


class MyTestEnum(Enum):
    OPTION_A = "option_a"
    OPTION_B = "option_b"


class AllTypesModel(AtomicRedisModel):
    str_field: str = "default"
    int_field: int = 0
    bool_field: bool = False
    datetime_field: datetime = datetime(2020, 1, 1)
    bytes_field: bytes = b""
    any_field: object = "default"
    enum_field: MyTestEnum = MyTestEnum.OPTION_A
    list_field: list[str] = Field(default_factory=list)
    dict_field: dict[str, str] = Field(default_factory=dict)
