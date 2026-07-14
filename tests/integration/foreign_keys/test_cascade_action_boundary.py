import pytest

from rapyer.result import CascadeResult
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

# Deliberately different from CASCADE_FIXTURE_TTL_SECONDS so a passing test
# proves the root-vs-child ttl split rather than a coincidental match.
ROOT_TTL_SECONDS = 120


pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")


@pytest.mark.asyncio
async def test_aset_ttl_cascade_true_healthy_splits_parent_and_child_ttl_and_reports_no_dangling(
    real_redis_client,
):
    # Arrange
    # A healthy parent -> child, child's special fields populated.
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()

    # Act
    result = await parent.aset_ttl(ROOT_TTL_SECONDS, cascade=True)

    # Assert
    # CascadeResult with zero dangling counts,
    # proven end-to-end against real Redis Stack, not just fakeredis.
    assert isinstance(result, CascadeResult)
    assert result.dangling_children == 0
    assert result.dangling_special == 0

    # Assert
    # The parent's own key refreshes to the caller-supplied root ttl...
    parent_ttl = await real_redis_client.ttl(parent.key)
    assert 0 < parent_ttl <= ROOT_TTL_SECONDS

    # ...while the cascade-reached child (+ its own special-field keys)
    # refreshes to ITS OWN configured Meta.ttl, a DIFFERENT value than the
    # caller-supplied root ttl (root-vs-child split, real Redis).
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
async def test_asave_auto_cascades_child_ttl_with_no_explicit_ttl_call(
    real_redis_client,
):
    # Arrange
    # A saved CascadeSpecialParent -> CascadeSpecialChild pair,
    # ttls reset to a known "-1" baseline before the action under test.
    child = await CascadeSpecialChild().asave()
    parent = await CascadeSpecialParent(child=child.key).asave()
    await real_redis_client.persist(parent.key)
    await real_redis_client.persist(child.key)

    # Act
    # An ordinary write with no explicit ttl/cascade call anywhere.
    await parent.asave()

    # Assert
    # The cascade-reached child's own key was automatically re-armed.
    assert await real_redis_client.ttl(child.key) > 0
