from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.fields import PriorityQueue
from rapyer.types.priority_queue import RedisPriorityQueue


class TaskQueueModel(AtomicRedisModel):
    """Model with a simple string priority queue."""

    name: str = ""
    tasks: PriorityQueue[str] = Field(default_factory=RedisPriorityQueue)


class MultiQueueModel(AtomicRedisModel):
    """Model with multiple priority queues."""

    name: str = ""
    high_priority_tasks: PriorityQueue[str] = Field(default_factory=RedisPriorityQueue)
    low_priority_tasks: PriorityQueue[str] = Field(default_factory=RedisPriorityQueue)


class IntQueueModel(AtomicRedisModel):
    """Model with integer priority queue."""

    name: str = ""
    numbers: PriorityQueue[int] = Field(default_factory=RedisPriorityQueue)


class DictQueueModel(AtomicRedisModel):
    """Model with dict priority queue (complex items)."""

    name: str = ""
    jobs: PriorityQueue[dict] = Field(default_factory=RedisPriorityQueue)
