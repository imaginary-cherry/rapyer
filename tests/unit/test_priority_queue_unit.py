"""Unit tests for RedisPriorityQueue that use fakeredis."""

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis

from rapyer.base import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.fields import PriorityQueue
from rapyer.types.priority_queue import RedisPriorityQueue, PriorityItem
from pydantic import Field


class TaskQueueModelUnit(AtomicRedisModel):
    name: str = ""
    tasks: PriorityQueue[str] = Field(default_factory=RedisPriorityQueue)

    Meta = RedisConfig(init_with_rapyer=False, prefer_normal_json_dump=True)


class MultiQueueModelUnit(AtomicRedisModel):
    name: str = ""
    high: PriorityQueue[str] = Field(default_factory=RedisPriorityQueue)
    low: PriorityQueue[str] = Field(default_factory=RedisPriorityQueue)

    Meta = RedisConfig(init_with_rapyer=False, prefer_normal_json_dump=True)


@pytest_asyncio.fixture
async def redis_client():
    """Create a fake Redis client for testing."""
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def task_model(redis_client):
    """Create a TaskQueueModel with the fake Redis client."""
    TaskQueueModelUnit.Meta.redis = redis_client
    model = TaskQueueModelUnit(name="test_queue")
    await model.asave()
    return model


@pytest.mark.asyncio
async def test_priority_item_dataclass():
    """Test PriorityItem dataclass."""
    item = PriorityItem(item="test", priority=5.0)
    assert item.item == "test"
    assert item.priority == 5.0

    # Test iteration (for unpacking)
    item_val, priority_val = item
    assert item_val == "test"
    assert priority_val == 5.0


@pytest.mark.asyncio
async def test_priority_queue_field_detection():
    """Test that priority queue fields are detected in model."""
    assert "tasks" in TaskQueueModelUnit._priority_queue_fields
    assert "high" in MultiQueueModelUnit._priority_queue_fields
    assert "low" in MultiQueueModelUnit._priority_queue_fields


@pytest.mark.asyncio
async def test_priority_queue_zset_key_format(task_model):
    """Test the ZSET key format."""
    expected_key = f"{task_model.key}:pq:tasks"
    assert task_model.tasks.zset_key == expected_key


@pytest.mark.asyncio
async def test_push_and_pop_max(task_model):
    """Test basic push and pop_max operations."""
    await task_model.tasks.apush("task1", priority=1.0)
    await task_model.tasks.apush("task2", priority=10.0)
    await task_model.tasks.apush("task3", priority=5.0)

    result = await task_model.tasks.apop_max()
    assert result is not None
    assert result.item == "task2"
    assert result.priority == 10.0


@pytest.mark.asyncio
async def test_push_and_pop_min(task_model):
    """Test push and pop_min operations."""
    await task_model.tasks.apush("low", priority=1.0)
    await task_model.tasks.apush("high", priority=10.0)
    await task_model.tasks.apush("mid", priority=5.0)

    result = await task_model.tasks.apop_min()
    assert result is not None
    assert result.item == "low"
    assert result.priority == 1.0


@pytest.mark.asyncio
async def test_peek_max(task_model):
    """Test peek_max doesn't remove items."""
    await task_model.tasks.apush("task1", priority=1.0)
    await task_model.tasks.apush("task2", priority=10.0)

    result = await task_model.tasks.apeek_max()
    assert result.item == "task2"

    # Item should still be there
    count = await task_model.tasks.alen()
    assert count == 2


@pytest.mark.asyncio
async def test_peek_min(task_model):
    """Test peek_min doesn't remove items."""
    await task_model.tasks.apush("task1", priority=1.0)
    await task_model.tasks.apush("task2", priority=10.0)

    result = await task_model.tasks.apeek_min()
    assert result.item == "task1"

    count = await task_model.tasks.alen()
    assert count == 2


@pytest.mark.asyncio
async def test_push_many(task_model):
    """Test pushing multiple items."""
    items = [("a", 1.0), ("b", 2.0), ("c", 3.0)]
    count = await task_model.tasks.apush_many(items)
    assert count == 3

    total = await task_model.tasks.alen()
    assert total == 3


@pytest.mark.asyncio
async def test_remove(task_model):
    """Test removing a specific item."""
    await task_model.tasks.apush("task1", priority=1.0)
    await task_model.tasks.apush("task2", priority=2.0)

    removed = await task_model.tasks.aremove("task1")
    assert removed is True

    count = await task_model.tasks.alen()
    assert count == 1


@pytest.mark.asyncio
async def test_remove_nonexistent(task_model):
    """Test removing a non-existent item."""
    removed = await task_model.tasks.aremove("nonexistent")
    assert removed is False


@pytest.mark.asyncio
async def test_update_priority(task_model):
    """Test updating an item's priority."""
    await task_model.tasks.apush("task1", priority=1.0)

    updated = await task_model.tasks.aupdate_priority("task1", 100.0)
    assert updated is True

    score = await task_model.tasks.ascore("task1")
    assert score == 100.0


@pytest.mark.asyncio
async def test_increment_priority(task_model):
    """Test incrementing an item's priority."""
    await task_model.tasks.apush("task1", priority=5.0)

    new_priority = await task_model.tasks.aincrement_priority("task1", 10.0)
    assert new_priority == 15.0


@pytest.mark.asyncio
async def test_score(task_model):
    """Test getting an item's score."""
    await task_model.tasks.apush("task1", priority=42.5)

    score = await task_model.tasks.ascore("task1")
    assert score == 42.5


@pytest.mark.asyncio
async def test_rank(task_model):
    """Test getting item ranks."""
    await task_model.tasks.apush("low", priority=1.0)
    await task_model.tasks.apush("mid", priority=5.0)
    await task_model.tasks.apush("high", priority=10.0)

    rank = await task_model.tasks.arank("mid")
    assert rank == 1  # Second lowest

    revrank = await task_model.tasks.arevrank("mid")
    assert revrank == 1  # Second highest


@pytest.mark.asyncio
async def test_contains(task_model):
    """Test contains operation."""
    await task_model.tasks.apush("task1", priority=1.0)

    exists = await task_model.tasks.acontains("task1")
    assert exists is True

    exists = await task_model.tasks.acontains("nonexistent")
    assert exists is False


@pytest.mark.asyncio
async def test_clear(task_model):
    """Test clearing the queue."""
    await task_model.tasks.apush("task1", priority=1.0)
    await task_model.tasks.apush("task2", priority=2.0)

    await task_model.tasks.aclear()

    count = await task_model.tasks.alen()
    assert count == 0


@pytest.mark.asyncio
async def test_range(task_model):
    """Test range operations."""
    await task_model.tasks.apush("a", priority=1.0)
    await task_model.tasks.apush("b", priority=2.0)
    await task_model.tasks.apush("c", priority=3.0)

    items = await task_model.tasks.arange()
    assert len(items) == 3
    assert items[0].item == "a"
    assert items[2].item == "c"


@pytest.mark.asyncio
async def test_range_by_score(task_model):
    """Test range by score operations."""
    await task_model.tasks.apush("a", priority=1.0)
    await task_model.tasks.apush("b", priority=5.0)
    await task_model.tasks.apush("c", priority=10.0)
    await task_model.tasks.apush("d", priority=15.0)

    items = await task_model.tasks.arange_by_score(4.0, 12.0)
    assert len(items) == 2
    assert items[0].item == "b"
    assert items[1].item == "c"


@pytest.mark.asyncio
async def test_count_by_score(task_model):
    """Test counting items in a score range."""
    await task_model.tasks.apush("a", priority=1.0)
    await task_model.tasks.apush("b", priority=5.0)
    await task_model.tasks.apush("c", priority=10.0)

    count = await task_model.tasks.acount_by_score(4.0, 12.0)
    assert count == 2


@pytest.mark.asyncio
async def test_items_with_scores(task_model):
    """Test getting all items with scores."""
    await task_model.tasks.apush("task1", priority=1.0)
    await task_model.tasks.apush("task2", priority=2.0)

    items = await task_model.tasks.aitems_with_scores()
    assert len(items) == 2
    assert all(isinstance(item, PriorityItem) for item in items)


@pytest.mark.asyncio
async def test_items_without_scores(task_model):
    """Test getting all items without scores."""
    await task_model.tasks.apush("task1", priority=1.0)
    await task_model.tasks.apush("task2", priority=2.0)

    items = await task_model.tasks.aitems()
    assert len(items) == 2
    assert "task1" in items
    assert "task2" in items


@pytest.mark.asyncio
async def test_empty_queue_operations(task_model):
    """Test operations on empty queue."""
    result = await task_model.tasks.apop_max()
    assert result is None

    result = await task_model.tasks.apop_min()
    assert result is None

    result = await task_model.tasks.apeek_max()
    assert result is None

    count = await task_model.tasks.alen()
    assert count == 0


@pytest.mark.asyncio
async def test_pop_multiple(task_model):
    """Test popping multiple items at once."""
    await task_model.tasks.apush("a", priority=1.0)
    await task_model.tasks.apush("b", priority=2.0)
    await task_model.tasks.apush("c", priority=3.0)
    await task_model.tasks.apush("d", priority=4.0)

    results = await task_model.tasks.apop_max(count=2)
    assert len(results) == 2
    assert results[0].item == "d"
    assert results[1].item == "c"


@pytest.mark.asyncio
async def test_model_delete_clears_queue(redis_client):
    """Test that deleting model clears the queue."""
    TaskQueueModelUnit.Meta.redis = redis_client
    model = TaskQueueModelUnit(name="test")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)

    zset_key = model.tasks.zset_key
    exists = await redis_client.exists(zset_key)
    assert exists == 1

    await model.adelete()

    exists = await redis_client.exists(zset_key)
    assert exists == 0


@pytest.mark.asyncio
async def test_multiple_queues_in_model(redis_client):
    """Test model with multiple priority queues."""
    MultiQueueModelUnit.Meta.redis = redis_client
    model = MultiQueueModelUnit(name="multi")
    await model.asave()

    await model.high.apush("urgent", priority=100.0)
    await model.low.apush("deferred", priority=1.0)

    high_count = await model.high.alen()
    low_count = await model.low.alen()

    assert high_count == 1
    assert low_count == 1

    # Verify they have different keys
    assert model.high.zset_key != model.low.zset_key
