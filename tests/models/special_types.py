from typing import Generic, TypeVar

from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.types.priority_queue import RedisPriorityQueue

T = TypeVar("T")


class PriorityQueueModel(AtomicRedisModel):
    name: str = "default"
    tasks: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue)


class PriorityQueueIntModel(AtomicRedisModel):
    label: str = "test"
    queue: RedisPriorityQueue[int] = Field(default_factory=RedisPriorityQueue)


class MixedSpecialModel(AtomicRedisModel):
    name: str = "mixed"
    count: int = 0
    tasks: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue)


class GenericPriorityQueueModel(AtomicRedisModel, Generic[T]):
    name: str = "default"
    tasks: RedisPriorityQueue[T] = Field(default_factory=RedisPriorityQueue)
