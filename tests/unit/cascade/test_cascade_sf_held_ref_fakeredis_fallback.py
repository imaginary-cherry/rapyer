import pytest

from rapyer.result import CascadeResult
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadePQRefParent,
    CascadeSetRefParent,
)

TTL_SECONDS = 120


@pytest.mark.asyncio
async def test_set_ref_parent_cascade_on_fakeredis_refreshes_root_and_container_not_member(
    setup_fake_redis_for_cascade_apply,
    fake_redis_client,
):
    # Arrange: fakeredis fast path refreshes only own keys, never SET members.
    author = await CascadeAuthor(name="author").asave()
    parent = await CascadeSetRefParent().asave()
    await parent.refs.aadd(ForeignKey(author.key))

    refs_key = RedisSet.special_field_key(parent.key, "refs")
    await fake_redis_client.persist(parent.key)
    await fake_redis_client.persist(refs_key)
    await fake_redis_client.persist(author.key)

    # Act
    result = await parent.aset_ttl(TTL_SECONDS, cascade=True)

    # Assert
    assert result == CascadeResult(
        dangling_children=0, dangling_special=0, mismatched_class=0
    )
    assert await fake_redis_client.ttl(parent.key) > 0
    assert await fake_redis_client.ttl(refs_key) > 0
    assert await fake_redis_client.ttl(author.key) in (-1, -2)


@pytest.mark.asyncio
async def test_pq_ref_parent_cascade_on_fakeredis_refreshes_root_and_container_not_member(
    setup_fake_redis_for_cascade_apply,
    fake_redis_client,
):
    # Arrange: same shape as the SET proof above, for the ZSET-backed PQ container.
    author = await CascadeAuthor(name="author").asave()
    parent = await CascadePQRefParent().asave()
    await parent.queue.apush(ForeignKey(author.key), priority=1.0)

    queue_key = RedisPriorityQueue.special_field_key(parent.key, "queue")
    await fake_redis_client.persist(parent.key)
    await fake_redis_client.persist(queue_key)
    await fake_redis_client.persist(author.key)

    # Act
    result = await parent.aset_ttl(TTL_SECONDS, cascade=True)

    # Assert
    assert result == CascadeResult(
        dangling_children=0, dangling_special=0, mismatched_class=0
    )
    assert await fake_redis_client.ttl(parent.key) > 0
    assert await fake_redis_client.ttl(queue_key) > 0
    assert await fake_redis_client.ttl(author.key) in (-1, -2)
