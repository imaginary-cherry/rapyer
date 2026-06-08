from typing import ClassVar, Generic, Optional, TypeVar

from pydantic import Field

from rapyer.base import AtomicRedisModel, RedisConfig
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from tests.models.simple_types import TTL_TEST_SECONDS

T = TypeVar("T")


class PriorityQueueModelBase(AtomicRedisModel, Generic[T]):
    tasks: RedisPriorityQueue[T] = Field(default_factory=RedisPriorityQueue)


class PriorityQueueModel(PriorityQueueModelBase[str]):
    name: str = "default"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=TTL_TEST_SECONDS)


class PriorityQueueIntModel(PriorityQueueModelBase[int]):
    label: str = "test"


class MixedSpecialModel(PriorityQueueModelBase[str]):
    name: str = "mixed"
    count: int = 0


class OptionalPriorityQueueModel(AtomicRedisModel):
    name: str = "default"
    tasks: Optional[RedisPriorityQueue[str]] = None


class GenericPriorityQueueModel(AtomicRedisModel, Generic[T]):
    name: str = "default"
    tasks: RedisPriorityQueue[T] = Field(default_factory=RedisPriorityQueue)


class SubSubPriorityQueueModel(PriorityQueueModel):
    extra: str = "sub_sub"


class OverriddenSpecialFieldModel(PriorityQueueModelBase[str]):
    tasks: int = 0  # redefine inherited special field as non-special


class PQContainerModel(AtomicRedisModel):
    inner_pq: PriorityQueueModel = Field(default_factory=PriorityQueueModel)
    outer_name: str = "container"


class InnerSameNamePQModel(AtomicRedisModel):
    label: str = "inner"
    tasks: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue)


class NestedSameNamePQModel(AtomicRedisModel):
    name: str = "outer"
    tasks: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue)
    inner: InnerSameNamePQModel = Field(default_factory=InnerSameNamePQModel)


class GenericRedisSetModel(AtomicRedisModel, Generic[T]):
    name: str = "default"
    count: int = 0
    tags: RedisSet[T] = Field(default_factory=RedisSet)


class OptionalRedisSetModel(AtomicRedisModel):
    name: str = "default"
    tags: Optional[RedisSet[str]] = None


class AutoMappedSetModel(AtomicRedisModel):
    name: str = "default"
    tags: set[str] = Field(default_factory=set)


class SubSubRedisSetModel(GenericRedisSetModel[str]):
    extra: str = "sub_sub"


class RedisSetContainerModel(AtomicRedisModel):
    inner_set: GenericRedisSetModel[str] = Field(
        default_factory=GenericRedisSetModel[str]
    )
    outer_name: str = "container"
