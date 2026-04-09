import json

import pytest

from tests.models.special_types import PriorityQueueModel


@pytest.mark.asyncio
async def test_priority_queue_save_push_verify_and_pop_order(real_redis_client):
    # Arrange - create and save model
    model = PriorityQueueModel(name="pq_integration")
    await model.asave()

    # Act - push items with varying priorities (out of order)
    await model.tasks.apush("low_priority", 3.0)
    await model.tasks.apush("high_priority", 1.0)
    await model.tasks.apush("medium_priority", 2.0)

    # Assert - verify items stored correctly in Redis sorted set
    raw_items = await real_redis_client.zrange(
        model.tasks.special_key, 0, -1, withscores=True
    )
    assert len(raw_items) == 3
    assert raw_items[0] == (json.dumps("high_priority"), 1.0)
    assert raw_items[1] == (json.dumps("medium_priority"), 2.0)
    assert raw_items[2] == (json.dumps("low_priority"), 3.0)

    # Act
    first = await model.tasks.apop()

    # Assert - check output of priority queue
    assert first == ("high_priority", 1.0)

    second = await model.tasks.apop()
    assert second == ("medium_priority", 2.0)

    third = await model.tasks.apop()
    assert third == ("low_priority", 3.0)
