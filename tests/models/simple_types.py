from datetime import datetime

from pydantic import Field

from rapyer.base import AtomicRedisModel, RedisConfig
from rapyer.types import (
    RedisFloat,
    RedisDatetimeTimestamp,
    RedisInt,
    RedisList,
    RedisDict,
)
from tests.models.common import TaskStatus, Priority

TTL_TEST_SECONDS = 24


class StrModel(AtomicRedisModel):
    name: str = ""
    description: str = "default"


class IntModel(AtomicRedisModel):
    count: int = 0
    score: int = 100


class FloatModel(AtomicRedisModel):
    value: RedisFloat = 0.0
    temperature: float = 20.5


class BoolModel(AtomicRedisModel):
    is_active: bool = False
    is_deleted: bool = True


class BytesModel(AtomicRedisModel):
    data: bytes = b""
    binary_content: bytes = b"default"


class DatetimeModel(AtomicRedisModel):
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class DatetimeTimestampModel(AtomicRedisModel):
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


class UserModelWithTTL(AtomicRedisModel):
    name: str = "test"
    age: int = 25
    active: bool = True
    tags: list[str] = Field(default_factory=list)
    settings: dict[str, str] = Field(default_factory=dict)

    Meta = RedisConfig(ttl=300)


class UserModelWithoutTTL(AtomicRedisModel):
    name: str = "test"
    age: int = 25


class NoneTestModel(AtomicRedisModel):
    optional_string: str | None = None
    optional_int: int | None = None
    optional_bool: bool | None = None
    optional_bytes: bytes | None = None
    optional_list: list[str] | None = None
    optional_dict: dict[str, str] | None = None


class TTLRefreshTestModel(AtomicRedisModel):
    name: str = "test"
    age: RedisInt = 25
    score: RedisFloat = 0.0
    tags: RedisList[str] = Field(default_factory=list)
    settings: RedisDict[str, str] = Field(default_factory=dict)

    Meta = RedisConfig(ttl=TTL_TEST_SECONDS)


class TTLRefreshDisabledModel(AtomicRedisModel):
    name: str = "test"
    age: RedisInt = 25
    tags: RedisList[str] = Field(default_factory=list)

    Meta = RedisConfig(ttl=TTL_TEST_SECONDS, refresh_ttl=False)
