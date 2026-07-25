import pytest

from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import (
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


async def _apply_cascade(real_redis_client, root):
    return await real_redis_client.fcall(
        type(root).Meta.cascade_function_name,
        1,
        root.key,
        type(root).__name__,
        SPECIAL_FIELD_KEY_PREFIX,
        type(root).Meta.ttl,
        1,
    )


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
    await _apply_cascade(real_redis_client, parent)

    # Assert
    assert await real_redis_client.ttl(parent.key) > 0
    assert await real_redis_client.ttl(author1.key) > 0
    assert await real_redis_client.ttl(author2.key) > 0


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
    await _apply_cascade(real_redis_client, parent)

    # Assert
    assert await real_redis_client.ttl(parent.key) > 0
    assert await real_redis_client.ttl(author.key) > 0


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
    result = await _apply_cascade(real_redis_client, parent)

    # Assert (no separate SF-dangling counter -- reuses the existing dangling shape)
    assert result == [1, 0]
    assert await real_redis_client.ttl(parent.key) > 0
    assert await real_redis_client.ttl(author.key) > 0


# --- Test D (CASF-07 self-ref in SET) ---


@pytest.mark.asyncio
async def test_set_ref_self_node_terminates_without_hanging(real_redis_client):
    # Arrange
    node = await CascadeSetRefSelfNode().asave()
    await node.peers.aadd(node.key)
    await real_redis_client.persist(node.key)

    # Act (bounded by the shared visited map; must not hang or error)
    await _apply_cascade(real_redis_client, node)

    # Assert
    assert await real_redis_client.ttl(node.key) > 0


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
    await _apply_cascade(real_redis_client, root)

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
    await _apply_cascade(real_redis_client, parent)

    # Assert
    assert await real_redis_client.ttl(parent.key) > 0
    assert await real_redis_client.ttl(author.key) > 0


# --- Test G (CASF-07 self-ref in PQ/ZSET) ---


@pytest.mark.asyncio
async def test_pq_ref_self_node_terminates_without_hanging(real_redis_client):
    # Arrange
    node = await CascadePQRefSelfNode().asave()
    await node.peers.apush(node.key, priority=1.0)
    await real_redis_client.persist(node.key)

    # Act (exercises the ZRANGE branch's cycle-safety, independent of Test D)
    await _apply_cascade(real_redis_client, node)

    # Assert
    assert await real_redis_client.ttl(node.key) > 0


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
    result = await _apply_cascade(real_redis_client, root)

    # Assert
    assert await real_redis_client.ttl(root.key) > 0
    assert await real_redis_client.ttl(child.key) > 0
    assert result == [0, 0]
