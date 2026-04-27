from typing import ClassVar, Generic, Optional, TypeVar

from pydantic import Field

from rapyer.base import AtomicRedisModel, RedisConfig
from rapyer.types.priority_queue import RedisPriorityQueue
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


class PQContainerModel(AtomicRedisModel):
    inner_pq: PriorityQueueModel = Field(default_factory=PriorityQueueModel)
    outer_name: str = "container"


