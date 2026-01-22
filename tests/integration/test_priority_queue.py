import pytest

from tests.models.priority_queue_types import (
    TaskQueueModel,
    MultiQueueModel,
    IntQueueModel,
    DictQueueModel,
)


@pytest.mark.asyncio
async def test_priority_queue_push_and_pop_max():
    """Test basic push and pop_max operations."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    # Push items with different priorities
    await model.tasks.apush("low_priority", priority=1.0)
    await model.tasks.apush("high_priority", priority=10.0)
    await model.tasks.apush("medium_priority", priority=5.0)

    # Pop should return highest priority first
    result = await model.tasks.apop_max()
    assert result is not None
    assert result.item == "high_priority"
    assert result.priority == 10.0

    # Next pop should return medium priority
    result = await model.tasks.apop_max()
    assert result.item == "medium_priority"
    assert result.priority == 5.0


@pytest.mark.asyncio
async def test_priority_queue_push_and_pop_min():
    """Test push and pop_min operations."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("low_priority", priority=1.0)
    await model.tasks.apush("high_priority", priority=10.0)
    await model.tasks.apush("medium_priority", priority=5.0)

    # Pop min should return lowest priority first
    result = await model.tasks.apop_min()
    assert result is not None
    assert result.item == "low_priority"
    assert result.priority == 1.0


@pytest.mark.asyncio
async def test_priority_queue_peek_operations():
    """Test peek operations that don't remove items."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)
    await model.tasks.apush("task2", priority=10.0)
    await model.tasks.apush("task3", priority=5.0)

    # Peek max should return highest without removing
    result = await model.tasks.apeek_max()
    assert result.item == "task2"
    assert result.priority == 10.0

    # Item should still be in queue
    count = await model.tasks.alen()
    assert count == 3

    # Peek min should return lowest without removing
    result = await model.tasks.apeek_min()
    assert result.item == "task1"
    assert result.priority == 1.0

    # Count should still be 3
    count = await model.tasks.alen()
    assert count == 3


@pytest.mark.asyncio
async def test_priority_queue_push_many():
    """Test pushing multiple items at once."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    items = [
        ("task1", 1.0),
        ("task2", 2.0),
        ("task3", 3.0),
        ("task4", 4.0),
    ]
    result = await model.tasks.apush_many(items)
    assert result == 4

    count = await model.tasks.alen()
    assert count == 4


@pytest.mark.asyncio
async def test_priority_queue_range_operations():
    """Test range and range_by_score operations."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)
    await model.tasks.apush("task2", priority=5.0)
    await model.tasks.apush("task3", priority=10.0)
    await model.tasks.apush("task4", priority=15.0)
    await model.tasks.apush("task5", priority=20.0)

    # Get all items sorted by priority (ascending)
    items = await model.tasks.arange()
    assert len(items) == 5
    assert items[0].item == "task1"
    assert items[4].item == "task5"

    # Get items by score range
    items = await model.tasks.arange_by_score(5.0, 15.0)
    assert len(items) == 3
    assert all(5.0 <= item.priority <= 15.0 for item in items)


@pytest.mark.asyncio
async def test_priority_queue_remove_operations():
    """Test remove and remove_many operations."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)
    await model.tasks.apush("task2", priority=2.0)
    await model.tasks.apush("task3", priority=3.0)

    # Remove specific item
    removed = await model.tasks.aremove("task2")
    assert removed is True

    count = await model.tasks.alen()
    assert count == 2

    # Remove non-existent item
    removed = await model.tasks.aremove("non_existent")
    assert removed is False


@pytest.mark.asyncio
async def test_priority_queue_update_priority():
    """Test updating priority of existing items."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)
    await model.tasks.apush("task2", priority=5.0)

    # Update priority of task1
    updated = await model.tasks.aupdate_priority("task1", 100.0)
    assert updated is True

    # Now task1 should have highest priority
    result = await model.tasks.apeek_max()
    assert result.item == "task1"
    assert result.priority == 100.0


@pytest.mark.asyncio
async def test_priority_queue_increment_priority():
    """Test incrementing priority of items."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=5.0)

    # Increment priority
    new_priority = await model.tasks.aincrement_priority("task1", 10.0)
    assert new_priority == 15.0

    # Decrement priority
    new_priority = await model.tasks.aincrement_priority("task1", -5.0)
    assert new_priority == 10.0


@pytest.mark.asyncio
async def test_priority_queue_score_and_rank():
    """Test score and rank operations."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)
    await model.tasks.apush("task2", priority=5.0)
    await model.tasks.apush("task3", priority=10.0)

    # Get score of an item
    score = await model.tasks.ascore("task2")
    assert score == 5.0

    # Get rank (position in ascending order)
    rank = await model.tasks.arank("task2")
    assert rank == 1  # 0-indexed, task2 is second lowest

    # Get reverse rank (position in descending order)
    revrank = await model.tasks.arevrank("task2")
    assert revrank == 1  # 0-indexed, task2 is second highest


@pytest.mark.asyncio
async def test_priority_queue_contains():
    """Test contains operation."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)

    # Check existence
    exists = await model.tasks.acontains("task1")
    assert exists is True

    exists = await model.tasks.acontains("non_existent")
    assert exists is False


@pytest.mark.asyncio
async def test_priority_queue_clear():
    """Test clear operation."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)
    await model.tasks.apush("task2", priority=2.0)

    count = await model.tasks.alen()
    assert count == 2

    # Clear the queue
    await model.tasks.aclear()

    count = await model.tasks.alen()
    assert count == 0


@pytest.mark.asyncio
async def test_priority_queue_count_by_score():
    """Test counting items within a score range."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)
    await model.tasks.apush("task2", priority=5.0)
    await model.tasks.apush("task3", priority=10.0)
    await model.tasks.apush("task4", priority=15.0)
    await model.tasks.apush("task5", priority=20.0)

    # Count items in score range
    count = await model.tasks.acount_by_score(5.0, 15.0)
    assert count == 3


@pytest.mark.asyncio
async def test_priority_queue_items_with_and_without_scores():
    """Test getting items with and without scores."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)
    await model.tasks.apush("task2", priority=5.0)

    # Get items with scores
    items = await model.tasks.aitems_with_scores()
    assert len(items) == 2
    assert all(hasattr(item, "priority") for item in items)

    # Get items without scores
    items = await model.tasks.aitems()
    assert len(items) == 2
    assert "task1" in items
    assert "task2" in items


@pytest.mark.asyncio
async def test_priority_queue_multiple_queues_in_model():
    """Test model with multiple priority queues."""
    model = MultiQueueModel(name="multi_queue")
    await model.asave()

    # Add items to both queues
    await model.high_priority_tasks.apush("urgent_task", priority=100.0)
    await model.low_priority_tasks.apush("deferred_task", priority=1.0)

    # Verify they are stored separately
    high_count = await model.high_priority_tasks.alen()
    low_count = await model.low_priority_tasks.alen()

    assert high_count == 1
    assert low_count == 1

    # Pop from high priority queue
    result = await model.high_priority_tasks.apop_max()
    assert result.item == "urgent_task"

    # Low priority queue should be unaffected
    low_count = await model.low_priority_tasks.alen()
    assert low_count == 1


@pytest.mark.asyncio
async def test_priority_queue_model_delete_clears_queue(real_redis_client):
    """Test that deleting the model also deletes the priority queue."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)
    await model.tasks.apush("task2", priority=2.0)

    # Verify queue exists
    zset_key = model.tasks.zset_key
    exists = await real_redis_client.exists(zset_key)
    assert exists == 1

    # Delete model
    await model.adelete()

    # Queue should also be deleted
    exists = await real_redis_client.exists(zset_key)
    assert exists == 0


@pytest.mark.asyncio
async def test_priority_queue_integer_items():
    """Test priority queue with integer items."""
    model = IntQueueModel(name="int_queue")
    await model.asave()

    await model.numbers.apush(100, priority=1.0)
    await model.numbers.apush(200, priority=5.0)
    await model.numbers.apush(300, priority=10.0)

    result = await model.numbers.apop_max()
    assert result.item == 300


@pytest.mark.asyncio
async def test_priority_queue_dict_items():
    """Test priority queue with dict items."""
    model = DictQueueModel(name="dict_queue")
    await model.asave()

    job1 = {"id": 1, "name": "Job 1", "status": "pending"}
    job2 = {"id": 2, "name": "Job 2", "status": "running"}

    await model.jobs.apush(job1, priority=1.0)
    await model.jobs.apush(job2, priority=10.0)

    # Pop highest priority job
    result = await model.jobs.apop_max()
    assert result.item == job2


@pytest.mark.asyncio
async def test_priority_queue_pop_multiple():
    """Test popping multiple items at once."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)
    await model.tasks.apush("task2", priority=2.0)
    await model.tasks.apush("task3", priority=3.0)
    await model.tasks.apush("task4", priority=4.0)
    await model.tasks.apush("task5", priority=5.0)

    # Pop top 3
    results = await model.tasks.apop_max(count=3)
    assert len(results) == 3
    assert results[0].item == "task5"
    assert results[1].item == "task4"
    assert results[2].item == "task3"

    # Verify only 2 remain
    count = await model.tasks.alen()
    assert count == 2


@pytest.mark.asyncio
async def test_priority_queue_empty_operations():
    """Test operations on empty queue."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    # Pop from empty queue
    result = await model.tasks.apop_max()
    assert result is None

    result = await model.tasks.apop_min()
    assert result is None

    # Peek from empty queue
    result = await model.tasks.apeek_max()
    assert result is None

    result = await model.tasks.apeek_min()
    assert result is None

    # Count of empty queue
    count = await model.tasks.alen()
    assert count == 0


@pytest.mark.asyncio
async def test_priority_queue_zset_key_format(real_redis_client):
    """Test that the ZSET key follows the expected format."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task1", priority=1.0)

    # Key should be in format: {ModelKey}:pq:{field_name}
    expected_key = f"{model.key}:pq:tasks"
    assert model.tasks.zset_key == expected_key

    # Verify key exists in Redis
    exists = await real_redis_client.exists(expected_key)
    assert exists == 1


@pytest.mark.asyncio
async def test_priority_queue_same_priority_items():
    """Test items with the same priority."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("task_a", priority=5.0)
    await model.tasks.apush("task_b", priority=5.0)
    await model.tasks.apush("task_c", priority=5.0)

    count = await model.tasks.alen()
    assert count == 3

    # Items should all be retrievable
    items = await model.tasks.aitems()
    assert len(items) == 3
    assert set(items) == {"task_a", "task_b", "task_c"}


@pytest.mark.asyncio
async def test_priority_queue_negative_priority():
    """Test items with negative priorities."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    await model.tasks.apush("negative", priority=-10.0)
    await model.tasks.apush("zero", priority=0.0)
    await model.tasks.apush("positive", priority=10.0)

    # Pop max should return positive
    result = await model.tasks.apop_max()
    assert result.item == "positive"

    # Pop min should return negative
    result = await model.tasks.apop_min()
    assert result.item == "negative"


@pytest.mark.asyncio
async def test_priority_queue_exists():
    """Test exists operation."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    # Queue doesn't exist yet (no items pushed)
    exists = await model.tasks.aexists()
    assert exists is False

    # Push an item
    await model.tasks.apush("task1", priority=1.0)

    # Now it exists
    exists = await model.tasks.aexists()
    assert exists is True


@pytest.mark.parametrize(
    ["priority_values"],
    [
        [[1.0, 2.0, 3.0, 4.0, 5.0]],
        [[0.1, 0.2, 0.3, 0.4, 0.5]],
        [[-5.0, -2.5, 0.0, 2.5, 5.0]],
    ],
)
@pytest.mark.asyncio
async def test_priority_queue_ordering(priority_values):
    """Test that items are ordered correctly by priority."""
    model = TaskQueueModel(name="test_queue")
    await model.asave()

    # Push items with various priorities
    for i, priority in enumerate(priority_values):
        await model.tasks.apush(f"task_{i}", priority=priority)

    # Get all items
    items = await model.tasks.arange()

    # Verify ascending order
    priorities = [item.priority for item in items]
    assert priorities == sorted(priority_values)
