import json

import pytest

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
