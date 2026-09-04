import pytest

from rapyer.result import CascadeResult
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

# Deliberately different from CASCADE_FIXTURE_TTL_SECONDS so a pass proves the ttl split.
ROOT_TTL_SECONDS = 120


pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")


@pytest.mark.asyncio
async def test_aset_ttl_cascade_true_healthy_splits_parent_and_child_ttl_and_reports_no_dangling(
    real_redis_client,
):
    # Arrange - a healthy parent -> child, with the child's special fields populated.
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()

    # Act
    result = await parent.aset_ttl(ROOT_TTL_SECONDS, cascade=True)

    # Assert - a CascadeResult with zero danglings, proven against real Redis Stack.
    assert isinstance(result, CascadeResult)
    assert result.dangling_children == 0
    assert result.dangling_special == 0

    # Assert - the parent's own key refreshes to the caller-supplied root ttl...
    parent_ttl = await real_redis_client.ttl(parent.key)
    assert 0 < parent_ttl <= ROOT_TTL_SECONDS

    # ...while the cascade-reached child refreshes to ITS OWN Meta.ttl, a different value.
    child_ttl = await real_redis_client.ttl(child.key)
    assert ROOT_TTL_SECONDS < child_ttl <= CASCADE_FIXTURE_TTL_SECONDS
    tags_ttl = await real_redis_client.ttl(
        RedisSet.special_field_key(child.key, "tags")
    )
    scores_ttl = await real_redis_client.ttl(
        RedisPriorityQueue.special_field_key(child.key, "scores")
    )
    assert ROOT_TTL_SECONDS < tags_ttl <= CASCADE_FIXTURE_TTL_SECONDS
    assert ROOT_TTL_SECONDS < scores_ttl <= CASCADE_FIXTURE_TTL_SECONDS


@pytest.mark.asyncio
async def test_aset_ttl_cascade_true_dangling_child_reports_count_without_raising(
    real_redis_client,
):
    # Arrange - the referenced child key is never created.
    parent = await CascadeSpecialParent(child="CascadeSpecialChild:missing").asave()
    await real_redis_client.persist(parent.key)

    # Act
    result = await parent.aset_ttl(ROOT_TTL_SECONDS, cascade=True)

    # Assert
    assert await real_redis_client.ttl(parent.key) > 0
    assert isinstance(result, CascadeResult)
    assert result.dangling_children == 1
    assert result.dangling_special == 2


@pytest.mark.asyncio
async def test_asave_auto_cascades_child_ttl_with_no_explicit_ttl_call(
    real_redis_client,
):
    # Arrange - a saved parent/child pair with ttls reset to a known -1 baseline.
    child = await CascadeSpecialChild().asave()
    parent = await CascadeSpecialParent(child=child.key).asave()
    await real_redis_client.persist(parent.key)
    await real_redis_client.persist(child.key)

    # Act - an ordinary write, with no explicit ttl or cascade call anywhere.
    await parent.asave()

    # Assert - the cascade-reached child's own key was automatically re-armed.
    assert await real_redis_client.ttl(child.key) > 0
