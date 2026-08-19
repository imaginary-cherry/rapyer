import inspect

import pytest

from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SpecialFieldType


def test_aprepare_special_is_not_abstract_sanity():
    # Arrange & Act
    is_abstract = getattr(
        SpecialFieldType.aprepare_special, "__isabstractmethod__", False
    )

    # Assert
    assert is_abstract is False


def test_aprepare_special_is_async():
    # Arrange & Act / Assert
    assert inspect.iscoroutinefunction(SpecialFieldType.aprepare_special)


@pytest.mark.asyncio
async def test_aprepare_special_default_no_op_on_redis_set_sanity():
    # Arrange
    field = RedisSet()

    # Act
    result = await field.aprepare_special()

    # Assert
    assert result is None
    assert set(field) == set()


@pytest.mark.asyncio
async def test_aprepare_special_default_no_op_on_redis_priority_queue_sanity():
    # Arrange
    field = RedisPriorityQueue()

    # Act
    result = await field.aprepare_special()

    # Assert
    assert result is None


def test_pending_embed_text_is_not_abstract_sanity():
    # Arrange & Act
    is_abstract = getattr(
        SpecialFieldType.pending_embed_text, "__isabstractmethod__", False
    )

    # Assert
    assert is_abstract is False


def test_pending_embed_text_default_no_op_on_redis_set_sanity():
    # Arrange
    field = RedisSet()

    # Act
    result = field.pending_embed_text()

    # Assert
    assert result is None


def test_pending_embed_text_default_no_op_on_redis_priority_queue_sanity():
    # Arrange
    field = RedisPriorityQueue()

    # Act
    result = field.pending_embed_text()

    # Assert
    assert result is None


def test_pending_embed_text_callable_directly_on_class_sanity():
    # Arrange
    field = RedisSet()

    # Act
    result = SpecialFieldType.pending_embed_text(field)

    # Assert
    assert result is None
