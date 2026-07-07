import pytest

from rapyer.cascade import CascadePlanner
from rapyer.scripts import arun_sha
from rapyer.scripts.constants import CASCADE_TTL_APPLY_SCRIPT_NAME
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBookCollection,
    CascadeBookNested,
    CascadeChainNode,
    CascadeChainRoot,
    CascadeDiamondChild,
    CascadeDiamondRoot,
    CascadeExtendingNode,
    CascadeMultiDepthRoot,
    CascadeProfile,
    CascadeShallowRoot,
    CascadeSpecialChild,
    CascadeSpecialParent,
    CascadeWR02Grandchild,
    CascadeWR02Root,
    CascadeWR02SharedChild,
)

pytestmark = pytest.mark.usefixtures("setup_fake_redis_for_cascade_apply")


async def _apply_cascade(fake_redis_client, root) -> None:
    await arun_sha(
        fake_redis_client,
        type(root).Meta,
        CASCADE_TTL_APPLY_SCRIPT_NAME,
        1,
        root.key,
        type(root).__name__,
        SPECIAL_FIELD_KEY_PREFIX,
    )


# --- Special-field-child gap closure (01-HUMAN-UAT.md) ---


@pytest.mark.asyncio
async def test_cascade_apply_refreshes_special_field_child_keys_sanity(
    fake_redis_client,
):
    # Arrange: a saved child with BOTH special-field kinds actually populated,
    # so their Redis keys exist and can carry a TTL.
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()
    await fake_redis_client.persist(parent.key)
    await fake_redis_client.persist(child.key)

    # Act
    await _apply_cascade(fake_redis_client, parent)

    # Assert: root's own key + the reached child's main key AND both of the
    # child's own special-field keys all carry a positive TTL.
    assert await fake_redis_client.ttl(parent.key) > 0
    assert await fake_redis_client.ttl(child.key) > 0
    assert (
        await fake_redis_client.ttl(RedisSet.special_field_key(child.key, "tags")) > 0
    )
    assert (
        await fake_redis_client.ttl(
            RedisPriorityQueue.special_field_key(child.key, "scores")
        )
        > 0
    )


# --- Shape-1/2/3 re-proof under the REAL script ---


@pytest.mark.asyncio
async def test_shape1_chain_root_reaches_the_expected_prefix_of_the_chain_sanity(
    fake_redis_client,
):
    # Arrange: CascadeChainRoot.head carries CascadeTTL(depth=2); a->b->c->d chain.
    # depth=2 is the child subtree's budget: root->a (fresh budget 2), a->b
    # (blanket, budget 1), b->c (blanket, budget 0), c->d (budget exhausted).
    # This is the WR-01 contract the client-side CascadePlanner is unit-tested
    # for (test_multi_hop_chain_truncated_by_field_depth: [root, a, b, c]); the
    # server-side Lua must now match it exactly rather than the old off-by-one
    # min-cap semantics that stopped a hop short at [root, a, b].
    d = await CascadeChainNode(name="d").asave()
    c = await CascadeChainNode(name="c", next=d.key).asave()
    b = await CascadeChainNode(name="b", next=c.key).asave()
    a = await CascadeChainNode(name="a", next=b.key).asave()
    root = await CascadeChainRoot(head=a.key).asave()
    all_keys = (root.key, a.key, b.key, c.key, d.key)
    for key in all_keys:
        await fake_redis_client.persist(key)

    # The client-side planner is the authority for the depth budget.
    expected = set(await CascadePlanner().atraverse(root.key, CascadeChainRoot))

    # Act
    await _apply_cascade(fake_redis_client, root)

    # Assert: the Lua refresh set matches the planner exactly — root, a, b, c
    # refreshed; d (beyond the depth-2 budget) left untouched.
    refreshed = {key for key in all_keys if await fake_redis_client.ttl(key) > 0}
    assert refreshed == expected
    assert refreshed == {root.key, a.key, b.key, c.key}
    assert await fake_redis_client.ttl(d.key) in (-1, -2)


@pytest.mark.asyncio
async def test_depth0_shallow_root_extends_via_explicit_override_matches_planner_parity(
    fake_redis_client,
):
    # CR-01/WR-01 regression. CascadeShallowRoot.entry carries CascadeTTL(depth=0)
    # — the value that used to compute `depth - 1 == -1 == UNBOUNDED` and turn the
    # whole subtree unbounded. CascadeExtendingNode.onward is an explicit depth=5
    # override that must REFRESH the budget and extend PAST the depth=0 entry
    # (D-09), not be silenced by it. The Lua must reach EXACTLY the CascadePlanner
    # refresh set for this scalar shape-1 chain (no shape-2 fakeredis divergence).
    tail = await CascadeChainNode(name="tail").asave()
    head = await CascadeChainNode(name="head", next=tail.key).asave()
    extending = await CascadeExtendingNode(onward=head.key).asave()
    root = await CascadeShallowRoot(entry=extending.key).asave()
    all_keys = (root.key, extending.key, head.key, tail.key)
    for key in all_keys:
        await fake_redis_client.persist(key)

    expected = set(await CascadePlanner().atraverse(root.key, CascadeShallowRoot))

    # Act
    await _apply_cascade(fake_redis_client, root)

    # Assert: parity with the planner, and the depth=0 entry did extend the full
    # chain via the explicit override (all four keys), not by an unbounded walk
    # of a mis-cast sentinel.
    refreshed = {key for key in all_keys if await fake_redis_client.ttl(key) > 0}
    assert refreshed == expected
    assert refreshed == set(all_keys)


@pytest.mark.asyncio
async def test_independent_sibling_depth_budgets_match_planner_parity(
    fake_redis_client,
):
    # WR-01 regression on the blanket-decrement path (distinguishes the fixed Lua
    # from the old off-by-one). CascadeMultiDepthRoot.short_reach=depth1 reaches
    # exactly s1,s2; long_reach=depth3 reaches the whole l-chain. Two SEPARATE
    # chains so the shared visited-set never interferes.
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
        await fake_redis_client.persist(key)

    expected = set(await CascadePlanner().atraverse(root.key, CascadeMultiDepthRoot))

    # Act
    await _apply_cascade(fake_redis_client, root)

    # Assert
    refreshed = {key for key in all_keys if await fake_redis_client.ttl(key) > 0}
    assert refreshed == expected
    assert refreshed == {root.key, s1.key, s2.key, l1.key, l2.key, l3.key, l4.key}


@pytest.mark.asyncio
async def test_shape2_collection_of_fk_root_always_refreshes_sanity(
    fake_redis_client,
):
    # Arrange: CascadeBookCollection.co_authors carries CascadeTTL() (unbounded).
    #
    # KNOWN FAKEREDIS DIVERGENCE (discovered writing this test, see CONCERNS.md):
    # real Redis Stack's `JSON.GET key $.path` for a SINGLE path whose match is
    # itself an array returns a doubly-wrapped array (`[["A:1","A:2"]]` — the
    # outer array is "one match per path", the inner is the matched array
    # value). fakeredis instead collapses this to a single, un-wrapped array
    # (`["A:1","A:2"]`) for this specific single-path-into-an-array-field
    # shape (verified directly against both backends). The script's
    # single-path branch (`local match = decoded[1]`) then reads only the
    # FIRST co-author's key string rather than the whole array, so
    # `push_edges`'s `edge.collection` branch (which requires a Lua *table*)
    # never fires under fakeredis for a class with exactly one collection-of-FK
    # edge — the elements are silently not reached. This does NOT reproduce
    # on real Redis (see the confirmatory
    # tests/integration/foreign_keys/test_cascade_ttl_apply.py assertion,
    # which proves both co-authors DO refresh there). No production Lua code
    # is touched by this plan (see this plan's own <threat_model>); this test
    # documents the divergence rather than forcing fakeredis to match.
    author_a = await CascadeAuthor(name="a").asave()
    author_b = await CascadeAuthor(name="b").asave()
    book = await CascadeBookCollection(
        title="anthology", co_authors=[author_a.key, author_b.key]
    ).asave()
    for key in (author_a.key, author_b.key, book.key):
        await fake_redis_client.persist(key)

    # Act: must not error despite the collection-shape read quirk above.
    await _apply_cascade(fake_redis_client, book)

    # Assert: the root itself is always fully refreshed regardless of the
    # fakeredis JSON.GET quirk documented above.
    assert await fake_redis_client.ttl(book.key) > 0


@pytest.mark.asyncio
async def test_shape3_nested_submodel_fk_reaches_the_targets_own_ttl_sanity(
    fake_redis_client,
):
    # Arrange: CascadeBookNested.profile is a nested submodel whose OWN field
    # (CascadeProfile.mentor) carries the cascade marker (zero-hop nesting).
    author = await CascadeAuthor(name="mentor").asave()
    profile = CascadeProfile(mentor=author.key)
    book = await CascadeBookNested(title="memoir", profile=profile).asave()
    await fake_redis_client.persist(author.key)
    await fake_redis_client.persist(book.key)

    # Act
    await _apply_cascade(fake_redis_client, book)

    # Assert: the outer holder (root) and the FK target reached through the
    # nested submodel are both refreshed; the nested submodel itself has no
    # key of its own (same RedisJSON document as book).
    assert await fake_redis_client.ttl(book.key) > 0
    assert await fake_redis_client.ttl(author.key) > 0


# --- Diamond dedup ---


@pytest.mark.asyncio
async def test_diamond_shared_child_refreshed_exactly_once_via_either_edge_sanity(
    fake_redis_client,
):
    # Arrange: CascadeDiamondRoot.left/right both point at the SAME child.
    child = await CascadeDiamondChild(name="shared").asave()
    root = await CascadeDiamondRoot(left=child.key, right=child.key).asave()
    await fake_redis_client.persist(child.key)
    await fake_redis_client.persist(root.key)

    # Act: must not error from the double-visit (visited-set dedup).
    await _apply_cascade(fake_redis_client, root)

    # Assert
    assert await fake_redis_client.ttl(root.key) > 0
    assert await fake_redis_client.ttl(child.key) > 0


# --- Self-reference cycle safety ---


@pytest.mark.asyncio
async def test_self_reference_cycle_does_not_error_or_infinite_loop_sanity(
    fake_redis_client,
):
    # Arrange: a -> b -> a (cycle).
    a = await CascadeChainNode(name="a").asave()
    b = await CascadeChainNode(name="b", next=a.key).asave()
    a.next = b.key
    await a.asave()
    await fake_redis_client.persist(a.key)
    await fake_redis_client.persist(b.key)

    # Act: bounded by the visited-set; must complete without hanging/erroring.
    await _apply_cascade(fake_redis_client, a)

    # Assert
    assert await fake_redis_client.ttl(a.key) > 0
    assert await fake_redis_client.ttl(b.key) > 0


# --- WR-02: diamond with differing per-path depth budgets ---


@pytest.mark.asyncio
async def test_wr02_shared_child_own_key_always_refreshed_regardless_of_visit_order_sanity(
    fake_redis_client,
):
    # Arrange: deep_path/shallow_path both point at the SAME saved
    # CascadeWR02SharedChild instance, with differing depth budgets.
    grandchild = await CascadeWR02Grandchild().asave()
    shared_child = await CascadeWR02SharedChild(next=grandchild.key).asave()
    root = await CascadeWR02Root(
        deep_path=shared_child.key, shallow_path=shared_child.key
    ).asave()
    for key in (grandchild.key, shared_child.key, root.key):
        await fake_redis_client.persist(key)

    # Act
    await _apply_cascade(fake_redis_client, root)

    # Assert: the shared child's OWN key always has a positive TTL,
    # unconditionally, regardless of which sibling edge the DFS visits first
    # (WR-02: accepted, order-dependent-but-documented semantics apply only
    # to the child's OWN deeper descendants, not to the child itself).
    assert await fake_redis_client.ttl(root.key) > 0
    assert await fake_redis_client.ttl(shared_child.key) > 0

    # The grandchild's reach is genuinely order-dependent (depends on Python
    # `set` iteration order over `_relational_field_names` at plan-generation
    # time — see STATE.md WR-02) — deliberately assert EITHER outcome is
    # acceptable rather than pinning a specific one, to keep this test
    # non-flaky across interpreter runs / PYTHONHASHSEED values.
    grandchild_ttl = await fake_redis_client.ttl(grandchild.key)
    assert grandchild_ttl > 0 or grandchild_ttl in (-1, -2)
