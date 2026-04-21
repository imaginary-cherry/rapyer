from datetime import datetime
from typing import ClassVar

from pydantic import Field

from rapyer.base import AtomicRedisModel, RedisConfig
from rapyer.types import (
    RedisDatetimeTimestamp,
    RedisDict,
    RedisFloat,
    RedisInt,
    RedisList,
)
from tests.models.common import Priority, TaskStatus
from tests.models.pipeline_base import PipelineActionModel

TTL_TEST_SECONDS = 24
USER_TTL = 300


class StrModel(PipelineActionModel):
    name: str = ""
    description: str = "default"


class IntModel(PipelineActionModel):
    count: int = 0
    score: int = 100


class FloatModel(PipelineActionModel):
    value: RedisFloat = 0.0
    temperature: float = 20.5

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=TTL_TEST_SECONDS)


class BoolModel(AtomicRedisModel):
    is_active: bool = False
    is_deleted: bool = True


class BytesModel(PipelineActionModel):
    data: bytes = b""
    binary_content: bytes = b"default"


class DatetimeModel(PipelineActionModel):
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class DatetimeTimestampModel(PipelineActionModel):
    created_at: RedisDatetimeTimestamp = Field(default_factory=datetime.now)
    updated_at: RedisDatetimeTimestamp = Field(default_factory=datetime.now)


class DatetimeListModel(AtomicRedisModel):
    dates: list[datetime] = Field(default_factory=list)


class DatetimeDictModel(AtomicRedisModel):
    event_dates: dict[str, datetime] = Field(default_factory=dict)


class TaskModel(AtomicRedisModel):
    name: str
    status: TaskStatus = TaskStatus.PENDING
    priority: Priority = Priority.MEDIUM


class UserModelWithTTL(PipelineActionModel):
    name: str = "test"
    age: int = 25
    active: bool = True
    tags: list[str] = Field(default_factory=list)
    settings: dict[str, str] = Field(default_factory=dict)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=USER_TTL)


class UserModelWithoutTTL(PipelineActionModel):
    name: str = "test"
    age: int = 25


class NoneTestModel(AtomicRedisModel):
    optional_string: str | None = None
    optional_int: int | None = None
    optional_bool: bool | None = None
    optional_bytes: bytes | None = None
    optional_list: list[str] | None = None
    optional_dict: dict[str, str] | None = None


class TTLRefreshTestModel(PipelineActionModel):
    name: str = "test"
    age: RedisInt = 25
    score: RedisFloat = 0.0
    tags: RedisList[str] = Field(default_factory=list)
    settings: RedisDict[str, str] = Field(default_factory=dict)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=TTL_TEST_SECONDS)


class TTLRefreshDisabledModel(PipelineActionModel):
    name: str = "test"
    age: RedisInt = 25
    score: RedisFloat = 0.0
    tags: RedisList[str] = Field(default_factory=list)
    settings: RedisDict[str, str] = Field(default_factory=dict)

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=TTL_TEST_SECONDS, refresh_ttl=False)
