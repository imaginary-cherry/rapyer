from typing import ClassVar

import pytest
import pytest_asyncio
from fakeredis import aioredis as fake_aioredis
from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.special import SpecialFieldType


class FakePriorityQueueModel(AtomicRedisModel):
    name: str = "default"
    tasks: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue)
    Meta: ClassVar[RedisConfig] = RedisConfig(is_fake_redis=True)


class FakeMixedModel(AtomicRedisModel):
    name: str = "mixed"
    count: int = 0
    tasks: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue)
    Meta: ClassVar[RedisConfig] = RedisConfig(is_fake_redis=True)


class FakePriorityQueueIntModel(AtomicRedisModel):
    label: str = "test"
    queue: RedisPriorityQueue[int] = Field(default_factory=RedisPriorityQueue)
    Meta: ClassVar[RedisConfig] = RedisConfig(is_fake_redis=True)


@pytest_asyncio.fixture
async def fake_redis():
    client = fake_aioredis.FakeRedis(decode_responses=True)
    FakePriorityQueueModel.Meta.redis = client
    FakeMixedModel.Meta.redis = client
    FakePriorityQueueIntModel.Meta.redis = client
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.mark.asyncio
async def test_save_and_load_model_with_pq(fake_redis):
    model = FakePriorityQueueModel(name="test_save")
    await model.asave()

    loaded = await FakePriorityQueueModel.aget(model.key)
    assert loaded.name == "test_save"
    assert isinstance(loaded.tasks, SpecialFieldType)
    assert loaded.tasks.special_key == f"{model.key}:tasks"


@pytest.mark.asyncio
async def test_pq_push_and_pop(fake_redis):
    model = FakePriorityQueueModel(name="push_pop")
    await model.asave()

    await model.tasks.apush("task_a", 3.0)
    await model.tasks.apush("task_b", 1.0)
    await model.tasks.apush("task_c", 2.0)

    result = await model.tasks.apop()
    assert result is not None
    value, score = result
    assert value == "task_b"
    assert score == 1.0


@pytest.mark.asyncio
async def test_pq_peek(fake_redis):
    model = FakePriorityQueueModel(name="peek")
    await model.asave()

    await model.tasks.apush("high", 10.0)
    await model.tasks.apush("low", 1.0)

    result = await model.tasks.apeek()
    assert result is not None
    value, score = result
    assert value == "low"
    assert score == 1.0

    # peek should not remove
    assert await model.tasks.asize() == 2


@pytest.mark.asyncio
async def test_pq_size(fake_redis):
    model = FakePriorityQueueModel(name="size")
    await model.asave()

    assert await model.tasks.asize() == 0

    await model.tasks.apush("a", 1.0)
    await model.tasks.apush("b", 2.0)
    assert await model.tasks.asize() == 2


@pytest.mark.asyncio
async def test_pq_clear(fake_redis):
    model = FakePriorityQueueModel(name="clear")
    await model.asave()

    await model.tasks.apush("a", 1.0)
    await model.tasks.apush("b", 2.0)
    assert await model.tasks.asize() == 2

    await model.tasks.aclear()
    assert await model.tasks.asize() == 0


@pytest.mark.asyncio
async def test_pq_items(fake_redis):
    model = FakePriorityQueueModel(name="items")
    await model.asave()

    await model.tasks.apush("c", 3.0)
    await model.tasks.apush("a", 1.0)
    await model.tasks.apush("b", 2.0)

    items = await model.tasks.aitems()
    assert len(items) == 3
    assert items[0] == ("a", 1.0)
    assert items[1] == ("b", 2.0)
    assert items[2] == ("c", 3.0)


@pytest.mark.asyncio
async def test_pq_remove(fake_redis):
    model = FakePriorityQueueModel(name="remove")
    await model.asave()

    await model.tasks.apush("a", 1.0)
    await model.tasks.apush("b", 2.0)
    await model.tasks.apush("c", 3.0)

    removed = await model.tasks.aremove("b")
    assert removed is True

    items = await model.tasks.aitems()
    assert len(items) == 2
    values = [v for v, _ in items]
    assert "b" not in values


@pytest.mark.asyncio
async def test_pq_remove_nonexistent(fake_redis):
    model = FakePriorityQueueModel(name="remove_none")
    await model.asave()

    await model.tasks.apush("a", 1.0)
    removed = await model.tasks.aremove("nonexistent")
    assert removed is False


@pytest.mark.asyncio
async def test_pq_push_many(fake_redis):
    model = FakePriorityQueueModel(name="push_many")
    await model.asave()

    await model.tasks.apush_many([
        ("task_a", 3.0),
        ("task_b", 1.0),
        ("task_c", 2.0),
    ])

    assert await model.tasks.asize() == 3
    items = await model.tasks.aitems()
    assert items[0] == ("task_b", 1.0)
    assert items[1] == ("task_c", 2.0)
    assert items[2] == ("task_a", 3.0)


@pytest.mark.asyncio
async def test_pq_pop_empty(fake_redis):
    model = FakePriorityQueueModel(name="pop_empty")
    await model.asave()

    result = await model.tasks.apop()
    assert result is None


@pytest.mark.asyncio
async def test_pq_peek_empty(fake_redis):
    model = FakePriorityQueueModel(name="peek_empty")
    await model.asave()

    result = await model.tasks.apeek()
    assert result is None


@pytest.mark.asyncio
async def test_delete_model_deletes_pq_key(fake_redis):
    model = FakePriorityQueueModel(name="delete")
    await model.asave()

    await model.tasks.apush("a", 1.0)
    assert await model.tasks.asize() == 1

    # Verify the sorted set key exists
    exists = await fake_redis.exists(model.tasks.special_key)
    assert exists

    await model.adelete()

    # Verify both keys are deleted
    model_exists = await fake_redis.exists(model.key)
    pq_exists = await fake_redis.exists(model.tasks.special_key)
    assert not model_exists
    assert not pq_exists


@pytest.mark.asyncio
async def test_mixed_model_save_and_load(fake_redis):
    model = FakeMixedModel(name="mixed_test", count=42)
    await model.asave()

    loaded = await FakeMixedModel.aget(model.key)
    assert loaded.name == "mixed_test"
    assert loaded.count == 42
    assert isinstance(loaded.tasks, SpecialFieldType)


@pytest.mark.asyncio
async def test_pq_survives_model_reload(fake_redis):
    model = FakePriorityQueueModel(name="reload")
    await model.asave()

    await model.tasks.apush("item1", 1.0)
    await model.tasks.apush("item2", 2.0)

    loaded = await FakePriorityQueueModel.aget(model.key)
    assert await loaded.tasks.asize() == 2

    items = await loaded.tasks.aitems()
    assert items[0] == ("item1", 1.0)
    assert items[1] == ("item2", 2.0)


@pytest.mark.asyncio
async def test_pq_int_values(fake_redis):
    model = FakePriorityQueueIntModel(label="int_test")
    await model.asave()

    await model.queue.apush(42, 1.0)
    await model.queue.apush(99, 2.0)

    result = await model.queue.apop()
    assert result is not None
    value, score = result
    assert value == 42
    assert score == 1.0


@pytest.mark.asyncio
async def test_insert_multiple_models_with_pq(fake_redis):
    m1 = FakePriorityQueueModel(name="model1")
    m2 = FakePriorityQueueModel(name="model2")

    await FakePriorityQueueModel.ainsert(m1, m2)

    loaded1 = await FakePriorityQueueModel.aget(m1.key)
    loaded2 = await FakePriorityQueueModel.aget(m2.key)

    assert loaded1.name == "model1"
    assert loaded2.name == "model2"
    assert isinstance(loaded1.tasks, SpecialFieldType)
    assert isinstance(loaded2.tasks, SpecialFieldType)


@pytest.mark.asyncio
async def test_redis_dump_excludes_pq_field(fake_redis):
    model = FakePriorityQueueModel(name="dump_test")
    dump = model.redis_dump()

    assert "name" in dump
    assert "tasks" not in dump
