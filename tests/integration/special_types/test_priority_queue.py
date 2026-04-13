import json

import pytest
import pytest_asyncio

from rapyer.base import AtomicRedisModel
from rapyer.types.priority_queue import PriorityQueueItem, RedisPriorityQueue
from tests.conftest import special_field_test_for
from tests.models.special_types import (
    GenericPriorityQueueModel,
    OptionalPriorityQueueModel,
)

PQ_INIT_PARAMS = [
    [GenericPriorityQueueModel[str], [("gamma", 3.0), ("alpha", 1.0), ("beta", 2.0)]],
    [GenericPriorityQueueModel[int], [(30, 3.0), (10, 1.0), (20, 2.0)]],
    [GenericPriorityQueueModel[float], [(3.14, 3.0), (1.1, 1.0), (2.72, 2.0)]],
    [GenericPriorityQueueModel[bool], [(True, 2.0), (False, 1.0)]],
]


@pytest_asyncio.fixture
async def saved_pq_model(request):
    model_class, items_with_priorities = request.param
    model = model_class()
    await model.asave()
    for value, priority in items_with_priorities:
        await model.tasks.apush(value, priority)
    return model, items_with_priorities


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
@special_field_test_for(AtomicRedisModel.asave, RedisPriorityQueue)
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
    ["model_class", "items_with_priorities"],
    PQ_INIT_PARAMS,
)
@pytest.mark.asyncio
async def test_priority_queue_push_many_and_verify_order(
    real_redis_client,
    model_class: type[GenericPriorityQueueModel],
    items_with_priorities,
):
    model = model_class()
    await model.asave()

    await model.tasks.apush_many(
        [PriorityQueueItem(value=v, priority=p) for v, p in items_with_priorities]
    )

    expected_sorted = sorted(items_with_priorities, key=lambda x: x[1])
    items = await model.tasks.aitems()
    assert len(items) == len(expected_sorted)
    for item, (expected_value, expected_priority) in zip(items, expected_sorted):
        assert item.value == expected_value


@pytest.mark.parametrize("saved_pq_model", PQ_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_priority_queue_peek_returns_lowest_without_removal(saved_pq_model):
    model, items_with_priorities = saved_pq_model
    expected_peek = sorted(items_with_priorities, key=lambda x: x[1])[0][0]

    result = await model.tasks.apeek()
    assert result == expected_peek

    assert await model.tasks.asize() == len(items_with_priorities)


@pytest.mark.parametrize(
    ["model_class", "items_with_priorities"],
    PQ_INIT_PARAMS,
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


@pytest.mark.parametrize("saved_pq_model", PQ_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_priority_queue_clear_removes_all_items(saved_pq_model):
    model, items_with_priorities = saved_pq_model

    assert await model.tasks.asize() == len(items_with_priorities)

    await model.tasks.aclear()

    assert await model.tasks.asize() == 0
    assert await model.tasks.apop() is None


@pytest.mark.parametrize("saved_pq_model", PQ_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_priority_queue_items_returns_sorted_priority_queue_items(saved_pq_model):
    model, items_with_priorities = saved_pq_model
    expected_items = [
        PriorityQueueItem(value=v, priority=p)
        for v, p in sorted(items_with_priorities, key=lambda x: x[1])
    ]

    items = await model.tasks.aitems()
    assert items == expected_items


@pytest.mark.parametrize("saved_pq_model", PQ_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_priority_queue_remove_specific_value(saved_pq_model):
    model, items_with_priorities = saved_pq_model
    sorted_items = sorted(items_with_priorities, key=lambda x: x[1])
    value_to_remove = sorted_items[-1][0]

    removed = await model.tasks.aremove(value_to_remove)
    assert removed is True

    assert await model.tasks.asize() == len(items_with_priorities) - 1

    items = await model.tasks.aitems()
    assert all(item.value != value_to_remove for item in items)

    removed_again = await model.tasks.aremove(value_to_remove)
    assert removed_again is False


@pytest.mark.parametrize("saved_pq_model", PQ_INIT_PARAMS, indirect=True)
@pytest.mark.asyncio
async def test_priority_queue_delete_special_clears_queue(
    real_redis_client, saved_pq_model
):
    model, items_with_priorities = saved_pq_model

    special_key = model.tasks.special_key
    assert await real_redis_client.exists(special_key) == 1

    await model.tasks.adelete_special()

    assert await real_redis_client.exists(special_key) == 0


@pytest.mark.asyncio
async def test_optional_priority_queue_set_after_init(real_redis_client):
    model = OptionalPriorityQueueModel()
    assert model.tasks is None

    await model.asave()

    model.tasks = RedisPriorityQueue()
    await model.tasks.apush("hello", 1.0)

    result = await model.tasks.apop()
    assert result == "hello"
