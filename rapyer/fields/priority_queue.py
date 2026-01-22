import dataclasses
from typing import TYPE_CHECKING, Annotated, Any, Generic, TypeAlias, TypeVar

from rapyer.types.priority_queue import RedisPriorityQueue


@dataclasses.dataclass(frozen=True)
class PriorityQueueAnnotation:
    """
    Marker annotation for priority queue fields.

    Fields marked with this annotation are stored in a separate Redis ZSET
    key rather than in the JSON document. This allows efficient priority-based
    operations using native Redis commands.
    """

    pass


T = TypeVar("T")


class _PriorityQueueType(Generic[T]):
    """
    Priority Queue field annotation for AtomicRedisModel.

    This creates a field that stores data in a separate Redis Sorted Set (ZSET),
    linked to the parent model. All sorting and queue operations are handled
    natively by Redis with O(log N) complexity.

    Usage:
        from rapyer.fields import PriorityQueue

        class TaskQueue(AtomicRedisModel):
            name: str
            tasks: PriorityQueue[str] = PriorityQueue()

        # Or with default factory
        from pydantic import Field
        class TaskQueue(AtomicRedisModel):
            name: str
            tasks: PriorityQueue[str] = Field(default_factory=RedisPriorityQueue)

    Features:
        - Uses Redis ZSET for O(log N) operations
        - No Lua scripts required
        - Automatic TTL synchronization with parent model
        - Transparent lifecycle management (delete with parent)

    Operations:
        - apush(item, priority): Add item with priority
        - apop_min()/apop_max(): Remove and return lowest/highest priority item
        - apeek_min()/apeek_max(): View without removing
        - aremove(item): Remove specific item
        - arange_by_score(min, max): Query by priority range
        - aupdate_priority(item, new_priority): Update item's priority
        - alen(): Get queue size

    Example:
        queue = TaskQueue(name="my_queue")
        await queue.asave()

        # Add tasks with priorities (higher = more important)
        await queue.tasks.apush("urgent_task", priority=100.0)
        await queue.tasks.apush("normal_task", priority=50.0)
        await queue.tasks.apush("low_task", priority=10.0)

        # Process highest priority first
        task = await queue.tasks.apop_max()
        print(task.item)  # "urgent_task"
        print(task.priority)  # 100.0

        # Query by priority range
        medium_tasks = await queue.tasks.arange_by_score(40, 60)

        # Check queue size
        size = await queue.tasks.alen()
    """

    def __new__(cls, typ: Any = None):
        if typ is None:
            return RedisPriorityQueue()

        return Annotated[RedisPriorityQueue[typ], PriorityQueueAnnotation()]

    def __class_getitem__(cls, item):
        return Annotated[RedisPriorityQueue[item], PriorityQueueAnnotation()]


PriorityQueue = _PriorityQueueType


if TYPE_CHECKING:
    PriorityQueue: TypeAlias = Annotated[RedisPriorityQueue[T], PriorityQueueAnnotation()]  # pragma: no cover
