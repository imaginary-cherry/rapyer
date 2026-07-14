from unittest.mock import patch

import pytest

from rapyer.result import CascadeResult
from rapyer.scripts.constants import CASCADE_TTL_APPLY_SCRIPT_NAME
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeBookPlain,
    CascadeChainNode,
    CascadeChainRoot,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

# Deliberately different from CASCADE_FIXTURE_TTL_SECONDS so a passing test
# proves the root-vs-child ttl split rather than a coincidental match.
ROOT_TTL_SECONDS = 120


pytestmark = pytest.mark.usefixtures("setup_fake_redis_for_cascade_apply")


@pytest.mark.asyncio
async def test_aset_ttl_cascade_true_healthy_splits_parent_and_child_ttl_and_reports_no_dangling(
    fake_redis_client,
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
    # CascadeResult with zero dangling counts.
    assert isinstance(result, CascadeResult)
    assert result.dangling_children == 0
    assert result.dangling_special == 0

    # Assert
    # The parent's own key refreshes to the caller-supplied root ttl...
    parent_ttl = await fake_redis_client.ttl(parent.key)
    assert 0 < parent_ttl <= ROOT_TTL_SECONDS

    # ...while the cascade-reached child (+ its own special-field keys)
    # refreshes to ITS OWN configured Meta.ttl, not the caller-supplied root
    # ttl -- proven by asserting the child's ttl is strictly greater
    # than the root ttl and bounded by its own Meta.ttl.
    child_ttl = await fake_redis_client.ttl(child.key)
    assert ROOT_TTL_SECONDS < child_ttl <= CASCADE_FIXTURE_TTL_SECONDS
    tags_ttl = await fake_redis_client.ttl(
        RedisSet.special_field_key(child.key, "tags")
    )
    scores_ttl = await fake_redis_client.ttl(
        RedisPriorityQueue.special_field_key(child.key, "scores")
    )
    assert ROOT_TTL_SECONDS < tags_ttl <= CASCADE_FIXTURE_TTL_SECONDS
    assert ROOT_TTL_SECONDS < scores_ttl <= CASCADE_FIXTURE_TTL_SECONDS


@pytest.mark.asyncio
async def test_aset_ttl_cascade_true_dangling_child_reports_count_without_raising(
    fake_redis_client,
):
    # Arrange
    # The referenced child key is never created.
    parent = await CascadeSpecialParent(child="CascadeSpecialChild:missing").asave()

    # Act
    # Must not raise despite the dangling reference.
    result = await parent.aset_ttl(ROOT_TTL_SECONDS, cascade=True)

    # Assert
    # The parent's own write still succeeds and refreshes...
    assert await fake_redis_client.ttl(parent.key) > 0
    # ...and the dangling child (+ its two special-field keys) are reported,
    # never raised.
    assert isinstance(result, CascadeResult)
    assert result.dangling_children == 1
    assert result.dangling_special == 2


@pytest.mark.asyncio
async def test_aset_ttl_without_cascade_flag_only_refreshes_parent_own_keys(
    fake_redis_client,
):
    # Arrange
    # A healthy parent -> child, with the child's
    # ttl reset to a known "-1" baseline before the action under test.
    child = await CascadeSpecialChild().asave()
    parent = await CascadeSpecialParent(child=child.key).asave()
    await fake_redis_client.persist(child.key)

    # Act
    # Cascade omitted entirely.
    result = await parent.aset_ttl(ROOT_TTL_SECONDS)

    # Assert
    # Legacy behavior -- only the parent's own key changes, the
    # child is never touched, and no CascadeResult is produced.
    assert result is None
    assert await fake_redis_client.ttl(parent.key) > 0
    assert await fake_redis_client.ttl(child.key) == -1


@pytest.mark.asyncio
async def test_asave_auto_cascades_child_ttl_with_no_explicit_ttl_call(
    fake_redis_client,
):
    # Arrange
    # A saved CascadeChainRoot -> CascadeChainNode pair, ttls reset
    # to a known "-1" baseline before the action under test.
    node = await CascadeChainNode(name="child").asave()
    root = await CascadeChainRoot(head=node.key).asave()
    await fake_redis_client.persist(root.key)
    await fake_redis_client.persist(node.key)

    # Act
    # An ordinary write with no explicit ttl/cascade call anywhere.
    await root.asave()

    # Assert
    # The cascade-reached node's own key was automatically re-armed.
    assert await fake_redis_client.ttl(node.key) > 0


@pytest.mark.asyncio
async def test_asave_on_non_cascade_model_refreshes_ttl_via_the_cascade_script(
    fake_redis_client,
):
    # refresh_ttl always routes through the cascade script now, so even a
    # non-cascade model's write refreshes its own keys via the script (with no
    # outgoing edges it simply re-arms them), rather than a per-key EXPIRE loop.
    with patch("rapyer.base.scripts_registry.run_sha") as mock_run_sha:
        await CascadeBookPlain(author="CascadeAuthor:fake").asave()

    assert mock_run_sha.call_count == 1
    assert mock_run_sha.call_args.args[1] == CASCADE_TTL_APPLY_SCRIPT_NAME
