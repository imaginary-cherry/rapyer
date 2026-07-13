import pytest
import pytest_asyncio

from rapyer.cascade.planner import build_cascade_plan
from rapyer.result import CascadeResult
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from tests.integration.foreign_keys.conftest import CASCADE_INTEGRATION_MODELS
from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

# Deliberately different from CASCADE_FIXTURE_TTL_SECONDS so a passing test
# proves the D-02 root-vs-child ttl split rather than a coincidental match.
ROOT_TTL_SECONDS = 120


@pytest_asyncio.fixture
async def setup_real_redis_for_action_boundary(setup_real_redis_for_cascade_apply):
    """
    Composes on top of ``setup_real_redis_for_cascade_apply`` (real-Redis
    wiring + a real ``register_scripts`` call) by additionally stashing
    ``_has_cascade`` on every class in ``CASCADE_INTEGRATION_MODELS``, using
    the exact same mechanism ``init_rapyer()`` uses (D-05), so the tests in
    this module drive the real ``refresh_ttl``/``aset_ttl`` cascade branches
    in ``rapyer/base.py`` against actual Redis Stack rather than the legacy
    per-key EXPIRE loop.
    """
    plan = build_cascade_plan(CASCADE_INTEGRATION_MODELS)
    original = {model: model._has_cascade for model in CASCADE_INTEGRATION_MODELS}
    for model in CASCADE_INTEGRATION_MODELS:
        model._has_cascade = bool(plan[model.__name__].fks)
    try:
        yield
    finally:
        for model in CASCADE_INTEGRATION_MODELS:
            model._has_cascade = original[model]


pytestmark = pytest.mark.usefixtures("setup_real_redis_for_action_boundary")


@pytest.mark.asyncio
async def test_aset_ttl_cascade_true_healthy_splits_parent_and_child_ttl_and_reports_no_dangling(
    real_redis_client,
):
    # Arrange: a healthy parent -> child, child's special fields populated.
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()

    # Act
    result = await parent.aset_ttl(ROOT_TTL_SECONDS, cascade=True)

    # Assert: CascadeResult with zero dangling counts (CASC-01/CASC-06),
    # proven end-to-end against real Redis Stack, not just fakeredis.
    assert isinstance(result, CascadeResult)
    assert result.dangling_children == 0
    assert result.dangling_special == 0

    # Assert: the parent's own key refreshes to the caller-supplied root ttl...
    parent_ttl = await real_redis_client.ttl(parent.key)
    assert 0 < parent_ttl <= ROOT_TTL_SECONDS

    # ...while the cascade-reached child (+ its own special-field keys)
    # refreshes to ITS OWN configured Meta.ttl, a DIFFERENT value than the
    # caller-supplied root ttl (D-02 root-vs-child split, real Redis).
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
    # Arrange: a saved CascadeSpecialParent -> CascadeSpecialChild pair,
    # ttls reset to a known "-1" baseline before the action under test.
    child = await CascadeSpecialChild().asave()
    parent = await CascadeSpecialParent(child=child.key).asave()
    await real_redis_client.persist(parent.key)
    await real_redis_client.persist(child.key)

    # Act: an ordinary write with no explicit ttl/cascade call anywhere (D-04).
    await parent.asave()

    # Assert: the cascade-reached child's own key was automatically re-armed.
    assert await real_redis_client.ttl(child.key) > 0
