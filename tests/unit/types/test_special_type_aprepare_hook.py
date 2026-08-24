import inspect

import pytest

from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SpecialFieldType


def test_aprepare_many_is_a_classmethod_sanity():
    # Arrange & Act / Assert
    assert isinstance(vars(SpecialFieldType)["aprepare_many"], classmethod)


def test_aprepare_many_is_async():
    # Arrange & Act / Assert
    assert inspect.iscoroutinefunction(SpecialFieldType.aprepare_many)


@pytest.mark.asyncio
async def test_aprepare_many_default_no_op_on_redis_set_sanity():
    # Arrange
    field = RedisSet()

    # Act
    result = await RedisSet.aprepare_many([field])

    # Assert
    assert result is None
    assert set(field) == set()


@pytest.mark.asyncio
async def test_aprepare_many_default_no_op_on_redis_priority_queue_sanity():
    # Arrange
    field = RedisPriorityQueue()

    # Act
    result = await RedisPriorityQueue.aprepare_many([field])

    # Assert
    assert result is None
