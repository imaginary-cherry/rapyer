import pytest
from redis.exceptions import ResponseError

from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

ROOT_TTL_SECONDS = 120

pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")


async def _saved_parent_child_with_persisted_keys(real_redis_client):
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()
    tags_key = RedisSet.special_field_key(child.key, "tags")
    scores_key = RedisPriorityQueue.special_field_key(child.key, "scores")
    # persist everything so only the cascade can bring TTLs back.
    for key in (parent.key, child.key, tags_key, scores_key):
        await real_redis_client.persist(key)
    return parent, child, tags_key, scores_key


@pytest.mark.asyncio
async def test_aset_ttl_self_heals_missing_cascade_function(real_redis_client):
    # Arrange
    parent, child, tags_key, scores_key = await _saved_parent_child_with_persisted_keys(
        real_redis_client
    )
    await real_redis_client.function_flush()
    # The function is genuinely gone: a raw FCALL now fails (RED baseline).
    with pytest.raises(ResponseError):
        await real_redis_client.fcall(
            type(parent).Meta.cascade_function_name,
            1,
            parent.key,
            type(parent).__name__,
            SPECIAL_FIELD_KEY_PREFIX,
            ROOT_TTL_SECONDS,
            1,
        )

    # Act - production path must transparently reload the function.
    await parent.aset_ttl(ROOT_TTL_SECONDS, cascade=True)

    # Assert
    assert await real_redis_client.ttl(parent.key) > 0
    for key in (child.key, tags_key, scores_key):
        child_ttl = await real_redis_client.ttl(key)
        assert 0 < child_ttl <= CASCADE_FIXTURE_TTL_SECONDS
    assert type(parent).Meta.cascade_function_name is not None


@pytest.mark.asyncio
async def test_refresh_ttl_self_heals_missing_cascade_function(real_redis_client):
    # Arrange
    parent, child, tags_key, scores_key = await _saved_parent_child_with_persisted_keys(
        real_redis_client
    )
    await real_redis_client.function_flush()

    # Act - refresh_ttl executes via pipeline_with_execution; must reload the function.
    await parent.refresh_ttl()

    # Assert
    assert await real_redis_client.ttl(parent.key) > 0
    for key in (child.key, tags_key, scores_key):
        assert await real_redis_client.ttl(key) > 0
    assert type(parent).Meta.cascade_function_name is not None
