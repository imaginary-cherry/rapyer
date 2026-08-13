import pytest

from rapyer.types.redis_set import RedisSet
from tests.integration.foreign_keys.conftest import apply_cascade
from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeAuthor,
    CascadeMixedEdgeSharedChild,
    CascadeMixedEdgeSharedChildRoot,
    CascadePQRefParent,
    CascadePQRefSelfNode,
    CascadeSetRefParent,
    CascadeSetRefSelfNode,
    CascadeSfDiamondChild,
    CascadeSfDiamondRoot,
)

pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")


# --- Test A (CASF-04): RedisSet[ForeignKey] reach ---


@pytest.mark.asyncio
async def test_set_ref_parent_reaches_and_refreshes_both_set_members(
    real_redis_client,
):
    # Arrange
    parent = await CascadeSetRefParent().asave()
    author1 = await CascadeAuthor(name="a1").asave()
    author2 = await CascadeAuthor(name="a2").asave()
    await parent.refs.aadd(author1.key)
    await parent.refs.aadd(author2.key)
    for key in (parent.key, author1.key, author2.key):
        await real_redis_client.persist(key)

    # Act
    await apply_cascade(real_redis_client, parent)

    # Assert (root and both SET-referenced members refresh to their own Meta.ttl)
    for key in (parent.key, author1.key, author2.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS


# --- Test B (CASF-05): RedisPriorityQueue[ForeignKey] reach ---


@pytest.mark.asyncio
async def test_pq_ref_parent_reaches_and_refreshes_pq_member(real_redis_client):
    # Arrange
    parent = await CascadePQRefParent().asave()
    author = await CascadeAuthor(name="a").asave()
    await parent.queue.apush(author.key, priority=1.0)
    for key in (parent.key, author.key):
        await real_redis_client.persist(key)

    # Act
    await apply_cascade(real_redis_client, parent)

    # Assert (root and the PQ-referenced member refresh to their own Meta.ttl)
    for key in (parent.key, author.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS


# --- Test C (CASF-06 dangling reuse, D-02) ---


@pytest.mark.asyncio
async def test_set_ref_dangling_member_reuses_existing_dangling_count(
    real_redis_client,
):
    # Arrange
    parent = await CascadeSetRefParent().asave()
    author = await CascadeAuthor(name="a").asave()
    await parent.refs.aadd(author.key)
    await parent.refs.aadd("CascadeAuthor:does-not-exist")
    for key in (parent.key, author.key):
        await real_redis_client.persist(key)

    # Act
    result = await apply_cascade(real_redis_client, parent)

    # Assert -- SF reuses the existing dangling shape; the third element is class drift.
    assert result == [1, 0, 0]
    for key in (parent.key, author.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS


# --- Test D (CASF-07 self-ref in SET) ---


@pytest.mark.asyncio
async def test_set_ref_self_node_terminates_without_hanging(real_redis_client):
    # Arrange
    node = await CascadeSetRefSelfNode().asave()
    await node.peers.aadd(node.key)
    await real_redis_client.persist(node.key)

    # Act (bounded by the shared visited map; must not hang or error)
    await apply_cascade(real_redis_client, node)

    # Assert
    assert 0 < await real_redis_client.ttl(node.key) <= CASCADE_FIXTURE_TTL_SECONDS


# --- Test E (CASF-07 mixed-edge max-budget-wins) ---


@pytest.mark.asyncio
async def test_mixed_edge_shared_child_walked_at_the_larger_sf_budget(
    real_redis_client,
):
    # Arrange
    c4 = await CascadeMixedEdgeSharedChild(name="c4").asave()
    c3 = await CascadeMixedEdgeSharedChild(name="c3", onward=c4.key).asave()
    c2 = await CascadeMixedEdgeSharedChild(name="c2", onward=c3.key).asave()
    c1 = await CascadeMixedEdgeSharedChild(name="c1", onward=c2.key).asave()
    head = await CascadeMixedEdgeSharedChild(name="head", onward=c1.key).asave()
    root = await CascadeMixedEdgeSharedChildRoot(shallow_inline=head.key).asave()
    await root.deep_set.aadd(head.key)
    all_keys = (root.key, head.key, c1.key, c2.key, c3.key, c4.key)
    for key in all_keys:
        await real_redis_client.persist(key)

    # Act
    await apply_cascade(real_redis_client, root)

    # Assert (deep_set depth=4 SF budget wins over shallow_inline depth=1)
    refreshed = {key for key in all_keys if await real_redis_client.ttl(key) > 0}
    assert refreshed == set(all_keys)


# --- Test F (threat-model tolerance) ---


@pytest.mark.asyncio
async def test_malformed_and_non_string_sf_members_are_tolerated(real_redis_client):
    # Arrange
    parent = await CascadeSetRefParent().asave()
    author = await CascadeAuthor(name="a").asave()
    await parent.refs.aadd(author.key)
    sf_key = RedisSet.special_field_key(parent.key, "refs")
    await real_redis_client.sadd(sf_key, "not-json", "42")
    for key in (parent.key, author.key):
        await real_redis_client.persist(key)

    # Act (must not raise despite the malformed/non-string members)
    await apply_cascade(real_redis_client, parent)

    # Assert
    for key in (parent.key, author.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS


@pytest.mark.asyncio
async def test_wrongtype_sf_container_key_is_tolerated_not_an_aborted_cascade(
    real_redis_client,
):
    # Arrange
    # This is the SOLE regression guard for the SF-container counterpart of the
    # inline WRONGTYPE-degradation fix (test_cascade_apply_skips_corrupt_
    # wrongtype_reached_target_sanity in test_cascade_ttl_apply.py): the sf_key
    # is a STRING, not a SET, so SMEMBERS raises WRONGTYPE inside push_sf_edge.
    parent = await CascadeSetRefParent().asave()
    sf_key = RedisSet.special_field_key(parent.key, "refs")
    await real_redis_client.set(sf_key, "not-a-set")
    await real_redis_client.persist(parent.key)

    # Act (must not raise/abort the whole FCALL despite the WRONGTYPE key)
    await apply_cascade(real_redis_client, parent)

    # Assert (root still refreshes even though the SF edge was a dead end)
    assert 0 < await real_redis_client.ttl(parent.key) <= CASCADE_FIXTURE_TTL_SECONDS


# --- Test G (CASF-07 self-ref in PQ/ZSET) ---


@pytest.mark.asyncio
async def test_pq_ref_self_node_terminates_without_hanging(real_redis_client):
    # Arrange
    node = await CascadePQRefSelfNode().asave()
    await node.peers.apush(node.key, priority=1.0)
    await real_redis_client.persist(node.key)

    # Act (exercises the ZRANGE branch's cycle-safety, independent of Test D)
    await apply_cascade(real_redis_client, node)

    # Assert
    assert 0 < await real_redis_client.ttl(node.key) <= CASCADE_FIXTURE_TTL_SECONDS


# --- Test H (CASF-07 SF-only dual-edge diamond) ---


@pytest.mark.asyncio
async def test_sf_only_dual_edge_diamond_shared_child_refreshed_exactly_once(
    real_redis_client,
):
    # Arrange
    child = await CascadeSfDiamondChild().asave()
    root = await CascadeSfDiamondRoot().asave()
    await root.left.aadd(child.key)
    await root.right.apush(child.key, priority=1.0)
    for key in (root.key, child.key):
        await real_redis_client.persist(key)

    # Act (must not error from the double-visit -- visited-map dedup across SET+ZSET)
    result = await apply_cascade(real_redis_client, root)

    # Assert
    for key in (root.key, child.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS
    assert result == [0, 0, 0]
