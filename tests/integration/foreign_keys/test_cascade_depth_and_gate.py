import pytest

from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBlanketLeaf,
    CascadeBlanketNestedHolder,
    CascadeBlanketNestedProfile,
    CascadeBlanketOptOut,
    CascadeBookNested,
    CascadeChainNode,
    CascadeExtendingNode,
    CascadeMaxBudgetRoot,
    CascadeMultiDepthRoot,
    CascadeNestedDepthRoot,
    CascadeProfile,
    CascadeShallowRoot,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")


async def _apply_cascade(real_redis_client, root, cascade=True):
    return await real_redis_client.fcall(
        type(root).Meta.cascade_function_name,
        1,
        root.key,
        type(root).__name__,
        SPECIAL_FIELD_KEY_PREFIX,
        type(root).Meta.ttl,
        1 if cascade else 0,
    )


# --- do_cascade gate (real-Redis-only; ported from the fakeredis unit tests) ---


@pytest.mark.asyncio
async def test_cascade_false_refreshes_only_root_not_the_fk_child(real_redis_client):
    # Arrange
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()
    tags_key = RedisSet.special_field_key(child.key, "tags")
    scores_key = RedisPriorityQueue.special_field_key(child.key, "scores")
    for key in (parent.key, child.key, tags_key, scores_key):
        await real_redis_client.persist(key)

    # Act
    await _apply_cascade(real_redis_client, parent, cascade=False)

    # Assert
    assert await real_redis_client.ttl(parent.key) > 0
    assert await real_redis_client.ttl(child.key) in (-1, -2)
    assert await real_redis_client.ttl(tags_key) in (-1, -2)
    assert await real_redis_client.ttl(scores_key) in (-1, -2)


@pytest.mark.asyncio
async def test_cascade_false_still_refreshes_roots_own_special_keys(real_redis_client):
    # Arrange
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    await real_redis_client.persist(child.key)

    # Act
    result = await _apply_cascade(real_redis_client, child, cascade=False)

    # Assert
    assert await real_redis_client.ttl(child.key) > 0
    assert (
        await real_redis_client.ttl(RedisSet.special_field_key(child.key, "tags")) > 0
    )
    assert (
        await real_redis_client.ttl(
            RedisPriorityQueue.special_field_key(child.key, "scores")
        )
        > 0
    )
    assert result == [0, 0]


# --- Dangling-count contract ---


@pytest.mark.asyncio
async def test_cascade_counts_fully_dangling_child_and_its_special_keys(
    real_redis_client,
):
    # Arrange
    parent = await CascadeSpecialParent(
        child="CascadeSpecialChild:does-not-exist"
    ).asave()
    await real_redis_client.persist(parent.key)

    # Act
    result = await _apply_cascade(real_redis_client, parent)

    # Assert
    assert result == [1, 2]


@pytest.mark.asyncio
async def test_cascade_counts_dangling_special_keys_on_an_existing_child(
    real_redis_client,
):
    # Arrange
    child = await CascadeSpecialChild().asave()
    parent = await CascadeSpecialParent(child=child.key).asave()
    await real_redis_client.persist(parent.key)
    await real_redis_client.persist(child.key)

    # Act
    result = await _apply_cascade(real_redis_client, parent)

    # Assert
    assert result == [0, 2]


# --- Depth-budget arithmetic ---


@pytest.mark.asyncio
async def test_depth0_shallow_root_extends_via_explicit_override(real_redis_client):
    # Arrange
    tail = await CascadeChainNode(name="tail").asave()
    head = await CascadeChainNode(name="head", next=tail.key).asave()
    extending = await CascadeExtendingNode(onward=head.key).asave()
    root = await CascadeShallowRoot(entry=extending.key).asave()
    all_keys = (root.key, extending.key, head.key, tail.key)
    for key in all_keys:
        await real_redis_client.persist(key)

    # Act
    await _apply_cascade(real_redis_client, root)

    # Assert
    refreshed = {key for key in all_keys if await real_redis_client.ttl(key) > 0}
    assert refreshed == set(all_keys)


@pytest.mark.asyncio
async def test_independent_sibling_depth_budgets(real_redis_client):
    # Arrange
    s4 = await CascadeChainNode(name="s4").asave()
    s3 = await CascadeChainNode(name="s3", next=s4.key).asave()
    s2 = await CascadeChainNode(name="s2", next=s3.key).asave()
    s1 = await CascadeChainNode(name="s1", next=s2.key).asave()
    l4 = await CascadeChainNode(name="l4").asave()
    l3 = await CascadeChainNode(name="l3", next=l4.key).asave()
    l2 = await CascadeChainNode(name="l2", next=l3.key).asave()
    l1 = await CascadeChainNode(name="l1", next=l2.key).asave()
    root = await CascadeMultiDepthRoot(short_reach=s1.key, long_reach=l1.key).asave()
    all_keys = (
        root.key,
        s1.key,
        s2.key,
        s3.key,
        s4.key,
        l1.key,
        l2.key,
        l3.key,
        l4.key,
    )
    for key in all_keys:
        await real_redis_client.persist(key)

    # Act
    await _apply_cascade(real_redis_client, root)

    # Assert
    refreshed = {key for key in all_keys if await real_redis_client.ttl(key) > 0}
    assert refreshed == {root.key, s1.key, s2.key, l1.key, l2.key, l3.key, l4.key}


@pytest.mark.asyncio
async def test_max_budget_wins_for_shared_child_reaches_full_deep_prefix(
    real_redis_client,
):
    # Arrange
    c4 = await CascadeChainNode(name="c4").asave()
    c3 = await CascadeChainNode(name="c3", next=c4.key).asave()
    c2 = await CascadeChainNode(name="c2", next=c3.key).asave()
    c1 = await CascadeChainNode(name="c1", next=c2.key).asave()
    shared = await CascadeChainNode(name="shared", next=c1.key).asave()
    root = await CascadeMaxBudgetRoot(
        deep_path=shared.key, shallow_path=shared.key
    ).asave()
    all_keys = (root.key, shared.key, c1.key, c2.key, c3.key, c4.key)
    for key in all_keys:
        await real_redis_client.persist(key)

    # Act
    await _apply_cascade(real_redis_client, root)

    # Assert
    refreshed = {key for key in all_keys if await real_redis_client.ttl(key) > 0}
    assert refreshed == set(all_keys)


# --- Nested inline sub-model (shape 3) ---


@pytest.mark.asyncio
async def test_nested_submodel_fk_reaches_the_targets_own_ttl(real_redis_client):
    # Arrange
    author = await CascadeAuthor(name="mentor").asave()
    profile = CascadeProfile(mentor=author.key)
    book = await CascadeBookNested(title="memoir", profile=profile).asave()
    await real_redis_client.persist(author.key)
    await real_redis_client.persist(book.key)

    # Act
    await _apply_cascade(real_redis_client, book)

    # Assert
    assert await real_redis_client.ttl(book.key) > 0
    assert await real_redis_client.ttl(author.key) > 0


@pytest.mark.asyncio
async def test_blanket_opt_out_field_stops_traversal_despite_blanket_global(
    real_redis_client,
):
    # Arrange
    leaf = await CascadeBlanketLeaf(name="leaf").asave()
    root = await CascadeBlanketOptOut(child=leaf.key).asave()
    await real_redis_client.persist(root.key)
    await real_redis_client.persist(leaf.key)

    # Act
    await _apply_cascade(real_redis_client, root)

    # Assert
    assert await real_redis_client.ttl(root.key) > 0
    assert await real_redis_client.ttl(leaf.key) in (-1, -2)


@pytest.mark.asyncio
async def test_nested_submodel_zero_hop_does_not_consume_depth_budget(
    real_redis_client,
):
    # Arrange
    mentor = await CascadeBlanketLeaf(name="mentor").asave()
    holder = await CascadeBlanketNestedHolder(
        profile=CascadeBlanketNestedProfile(mentor=mentor.key)
    ).asave()
    root = await CascadeNestedDepthRoot(holder=holder.key).asave()
    for key in (root.key, holder.key, mentor.key):
        await real_redis_client.persist(key)

    # Act
    await _apply_cascade(real_redis_client, root)

    # Assert
    refreshed = {
        key
        for key in (root.key, holder.key, mentor.key)
        if await real_redis_client.ttl(key) > 0
    }
    assert refreshed == {root.key, holder.key, mentor.key}


@pytest.mark.asyncio
async def test_node_beyond_nested_depth_budget_is_never_reached(real_redis_client):
    # Arrange
    beyond = await CascadeBlanketLeaf(name="beyond").asave()
    mentor = await CascadeBlanketLeaf(name="mentor", onward=beyond.key).asave()
    holder = await CascadeBlanketNestedHolder(
        profile=CascadeBlanketNestedProfile(mentor=mentor.key)
    ).asave()
    root = await CascadeNestedDepthRoot(holder=holder.key).asave()
    for key in (root.key, holder.key, mentor.key, beyond.key):
        await real_redis_client.persist(key)

    # Act
    await _apply_cascade(real_redis_client, root)

    # Assert
    refreshed = {
        key
        for key in (root.key, holder.key, mentor.key)
        if await real_redis_client.ttl(key) > 0
    }
    assert refreshed == {root.key, holder.key, mentor.key}
    assert await real_redis_client.ttl(beyond.key) in (-1, -2)
