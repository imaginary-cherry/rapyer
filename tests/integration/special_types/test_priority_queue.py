import json

import pytest

from rapyer.types.priority_queue import PriorityQueueItem
from tests.models.special_types import GenericPriorityQueueModel


@pytest.mark.parametrize(
    ["model_class", "items_with_priorities", "expected_pop_order"],
    [
        [
            GenericPriorityQueueModel[str],
            [("low_priority", 3.0), ("high_priority", 1.0), ("medium_priority", 2.0)],
            ["high_priority", "medium_priority", "low_priority"],
        ],
        [
            GenericPriorityQueueModel[int],
            [(30, 3.0), (10, 1.0), (20, 2.0)],
            [10, 20, 30],
        ],
        [
            GenericPriorityQueueModel[float],
            [(3.14, 3.0), (1.1, 1.0), (2.72, 2.0)],
            [1.1, 2.72, 3.14],
        ],
        [
            GenericPriorityQueueModel[bool],
            [(True, 2.0), (False, 1.0)],
            [False, True],
        ],
    ],
)
@pytest.mark.asyncio
async def test_priority_queue_save_push_verify_and_pop_order(
    real_redis_client,
    model_class: type[GenericPriorityQueueModel],
    items_with_priorities,
    expected_pop_order,
):
    # Arrange - create and save model
    model = model_class()
    await model.asave()

    # Act - push items with varying priorities (out of order)
    for value, priority in items_with_priorities:
        await model.tasks.apush(value, priority)

    # Assert - verify items stored correctly in Redis sorted set
    raw_items = await real_redis_client.zrange(
        model.tasks.special_key, 0, -1, withscores=True
    )
    assert len(raw_items) == len(items_with_priorities)
    for raw_item, expected_value in zip(raw_items, expected_pop_order):
        member, score = raw_item
        assert json.loads(member) == expected_value

    # Act & Assert - pop items and verify priority order
    for expected_value in expected_pop_order:
        result = await model.tasks.apop()
        assert result == expected_value

    # Assert - queue is empty
    assert await model.tasks.asize() == 0
    assert await model.tasks.apop() is None


@pytest.mark.parametrize(
    ["model_class", "items_with_priorities", "expected_sorted_values"],
    [
        [
            GenericPriorityQueueModel[str],
            [("gamma", 3.0), ("alpha", 1.0), ("beta", 2.0)],
            ["alpha", "beta", "gamma"],
        ],
        [
            GenericPriorityQueueModel[int],
            [(30, 3.0), (10, 1.0), (20, 2.0)],
            [10, 20, 30],
        ],
        [
            GenericPriorityQueueModel[float],
            [(3.14, 3.0), (1.1, 1.0), (2.72, 2.0)],
            [1.1, 2.72, 3.14],
        ],
        [
            GenericPriorityQueueModel[bool],
            [(True, 2.0), (False, 1.0)],
            [False, True],
        ],
    ],
)
@pytest.mark.asyncio
async def test_priority_queue_push_many_and_verify_order(
    real_redis_client,
    model_class: type[GenericPriorityQueueModel],
    items_with_priorities,
    expected_sorted_values,
):
    model = model_class()
    await model.asave()

    await model.tasks.apush_many(items_with_priorities)

    items = await model.tasks.aitems()
    assert len(items) == len(expected_sorted_values)
    for item, expected_value in zip(items, expected_sorted_values):
        assert item.value == expected_value


@pytest.mark.parametrize(
    ["model_class", "items_with_priorities", "expected_peek_value"],
    [
        [
            GenericPriorityQueueModel[str],
            [("gamma", 3.0), ("alpha", 1.0), ("beta", 2.0)],
            "alpha",
        ],
        [
            GenericPriorityQueueModel[int],
            [(30, 3.0), (10, 1.0), (20, 2.0)],
            10,
        ],
        [
            GenericPriorityQueueModel[float],
            [(3.14, 3.0), (1.1, 1.0), (2.72, 2.0)],
            1.1,
        ],
        [
            GenericPriorityQueueModel[bool],
            [(True, 2.0), (False, 1.0)],
            False,
        ],
    ],
)
@pytest.mark.asyncio
async def test_priority_queue_peek_returns_lowest_without_removal(
    real_redis_client,
    model_class: type[GenericPriorityQueueModel],
    items_with_priorities,
    expected_peek_value,
):
    model = model_class()
    await model.asave()

    for value, priority in items_with_priorities:
        await model.tasks.apush(value, priority)

    result = await model.tasks.apeek()
    assert result == expected_peek_value

    assert await model.tasks.asize() == len(items_with_priorities)


@pytest.mark.parametrize(
    ["model_class", "items_with_priorities"],
    [
        [
            GenericPriorityQueueModel[str],
            [("gamma", 3.0), ("alpha", 1.0), ("beta", 2.0)],
        ],
        [
            GenericPriorityQueueModel[int],
            [(30, 3.0), (10, 1.0), (20, 2.0)],
        ],
        [
            GenericPriorityQueueModel[float],
            [(3.14, 3.0), (1.1, 1.0), (2.72, 2.0)],
        ],
        [
            GenericPriorityQueueModel[bool],
            [(True, 2.0), (False, 1.0)],
        ],
    ],
)
@pytest.mark.asyncio
async def test_priority_queue_size_reflects_operations(
    real_redis_client,
    model_class: type[GenericPriorityQueueModel],
    items_with_priorities,
):
    model = model_class()
    await model.asave()

    assert await model.tasks.asize() == 0

    for value, priority in items_with_priorities:
        await model.tasks.apush(value, priority)

    assert await model.tasks.asize() == len(items_with_priorities)

    await model.tasks.apop()
    assert await model.tasks.asize() == len(items_with_priorities) - 1


@pytest.mark.parametrize(
    ["model_class", "items_with_priorities"],
    [
        [
            GenericPriorityQueueModel[str],
            [("gamma", 3.0), ("alpha", 1.0), ("beta", 2.0)],
        ],
        [
            GenericPriorityQueueModel[int],
            [(30, 3.0), (10, 1.0), (20, 2.0)],
        ],
        [
            GenericPriorityQueueModel[float],
            [(3.14, 3.0), (1.1, 1.0), (2.72, 2.0)],
        ],
        [
            GenericPriorityQueueModel[bool],
            [(True, 2.0), (False, 1.0)],
        ],
    ],
)
@pytest.mark.asyncio
async def test_priority_queue_clear_removes_all_items(
    real_redis_client,
    model_class: type[GenericPriorityQueueModel],
    items_with_priorities,
):
    model = model_class()
    await model.asave()

    for value, priority in items_with_priorities:
        await model.tasks.apush(value, priority)

    assert await model.tasks.asize() == len(items_with_priorities)

    await model.tasks.aclear()

    assert await model.tasks.asize() == 0
    assert await model.tasks.apop() is None


@pytest.mark.parametrize(
    ["model_class", "items_with_priorities", "expected_items"],
    [
        [
            GenericPriorityQueueModel[str],
            [("gamma", 3.0), ("alpha", 1.0), ("beta", 2.0)],
            [
                PriorityQueueItem(value="alpha", priority=1.0),
                PriorityQueueItem(value="beta", priority=2.0),
                PriorityQueueItem(value="gamma", priority=3.0),
            ],
        ],
        [
            GenericPriorityQueueModel[int],
            [(30, 3.0), (10, 1.0), (20, 2.0)],
            [
                PriorityQueueItem(value=10, priority=1.0),
                PriorityQueueItem(value=20, priority=2.0),
                PriorityQueueItem(value=30, priority=3.0),
            ],
        ],
        [
            GenericPriorityQueueModel[float],
            [(3.14, 3.0), (1.1, 1.0), (2.72, 2.0)],
            [
                PriorityQueueItem(value=1.1, priority=1.0),
                PriorityQueueItem(value=2.72, priority=2.0),
                PriorityQueueItem(value=3.14, priority=3.0),
            ],
        ],
        [
            GenericPriorityQueueModel[bool],
            [(True, 2.0), (False, 1.0)],
            [
                PriorityQueueItem(value=False, priority=1.0),
                PriorityQueueItem(value=True, priority=2.0),
            ],
        ],
    ],
)
@pytest.mark.asyncio
async def test_priority_queue_items_returns_sorted_priority_queue_items(
    real_redis_client,
    model_class: type[GenericPriorityQueueModel],
    items_with_priorities,
    expected_items,
):
    model = model_class()
    await model.asave()

    for value, priority in items_with_priorities:
        await model.tasks.apush(value, priority)

    items = await model.tasks.aitems()
    assert items == expected_items


@pytest.mark.parametrize(
    ["model_class", "items_with_priorities", "value_to_remove"],
    [
        [
            GenericPriorityQueueModel[str],
            [("gamma", 3.0), ("alpha", 1.0), ("beta", 2.0)],
            "beta",
        ],
        [
            GenericPriorityQueueModel[int],
            [(30, 3.0), (10, 1.0), (20, 2.0)],
            20,
        ],
        [
            GenericPriorityQueueModel[float],
            [(3.14, 3.0), (1.1, 1.0), (2.72, 2.0)],
            2.72,
        ],
        [
            GenericPriorityQueueModel[bool],
            [(True, 2.0), (False, 1.0)],
            True,
        ],
    ],
)
@pytest.mark.asyncio
async def test_priority_queue_remove_specific_value(
    real_redis_client,
    model_class: type[GenericPriorityQueueModel],
    items_with_priorities,
    value_to_remove,
):
    model = model_class()
    await model.asave()

    for value, priority in items_with_priorities:
        await model.tasks.apush(value, priority)

    removed = await model.tasks.aremove(value_to_remove)
    assert removed is True

    assert await model.tasks.asize() == len(items_with_priorities) - 1

    items = await model.tasks.aitems()
    assert all(item.value != value_to_remove for item in items)

    removed_again = await model.tasks.aremove(value_to_remove)
    assert removed_again is False


@pytest.mark.parametrize(
    ["model_class", "items_with_priorities"],
    [
        [
            GenericPriorityQueueModel[str],
            [("gamma", 3.0), ("alpha", 1.0), ("beta", 2.0)],
        ],
        [
            GenericPriorityQueueModel[int],
            [(30, 3.0), (10, 1.0), (20, 2.0)],
        ],
        [
            GenericPriorityQueueModel[float],
            [(3.14, 3.0), (1.1, 1.0), (2.72, 2.0)],
        ],
        [
            GenericPriorityQueueModel[bool],
            [(True, 2.0), (False, 1.0)],
        ],
    ],
)
@pytest.mark.asyncio
async def test_priority_queue_delete_model_clears_queue(
    real_redis_client,
    model_class: type[GenericPriorityQueueModel],
    items_with_priorities,
):
    model = model_class()
    await model.asave()

    for value, priority in items_with_priorities:
        await model.tasks.apush(value, priority)

    special_key = model.tasks.special_key
    assert await real_redis_client.exists(special_key) == 1

    await model.tasks.adelete_special()

    assert await real_redis_client.exists(special_key) == 0
