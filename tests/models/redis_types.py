from typing import Annotated

from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.types.byte import RedisBytes
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.string import RedisStr


# Models with direct Redis type annotations
class DirectRedisStringModel(AtomicRedisModel):
    name: RedisStr = ""


class DirectRedisIntModel(AtomicRedisModel):
    count: RedisInt = 0


class DirectRedisBytesModel(AtomicRedisModel):
    data: RedisBytes = b""


class DirectRedisListModel(AtomicRedisModel):
    items: RedisList[str] = Field(default_factory=list)


class DirectRedisListIntModel(AtomicRedisModel):
    numbers: RedisList[int] = Field(default_factory=list)


class DirectRedisDictModel(AtomicRedisModel):
    metadata: RedisDict[str] = Field(default_factory=dict)


class DirectRedisDictIntModel(AtomicRedisModel):
    counters: RedisDict[int] = Field(default_factory=dict)


class MixedDirectRedisTypesModel(AtomicRedisModel):
    name: RedisStr = "default"
    count: RedisInt = 0
    active: bool = True
    tags: RedisList[str] = Field(default_factory=list)
    config: RedisDict[int] = Field(default_factory=dict)


class AnnotatedDirectRedisTypesModel(AtomicRedisModel):
    title: Annotated[RedisStr, Field(description="Title field")] = "default_title"
    score: Annotated[RedisInt, Field(ge=0, description="Score field")] = 0
    enabled: Annotated[bool, Field(description="Enabled flag")] = False
    categories: Annotated[RedisList[str], Field(description="Categories list")] = Field(
        default_factory=list
    )
    settings: Annotated[RedisDict[str], Field(description="Settings dict")] = Field(
        default_factory=dict
    )


class PipelineAllTypesTestModel(AtomicRedisModel):
    counter: int = 0
    amount: float = 0.0
    name: str = ""
    data: bytes = b""
    items: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
