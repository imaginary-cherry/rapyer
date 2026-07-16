import pytest

from rapyer.scripts import arun_sha
from rapyer.scripts.constants import CASCADE_TTL_APPLY_SCRIPT_NAME
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import CASCADE_PLAN_KEY, SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBlanketLeaf,
    CascadeBlanketNestedHolder,
    CascadeBlanketNestedProfile,
    CascadeBlanketOptOut,
    CascadeBookCollection,
    CascadeBookNested,
    CascadeChainNode,
    CascadeChainRoot,
    CascadeDiamondChild,
    CascadeDiamondRoot,
    CascadeExtendingNode,
    CascadeMaxBudgetRoot,
    CascadeMultiDepthRoot,
    CascadeNestedDepthRoot,
    CascadeProfile,
    CascadeShallowRoot,
    CascadeSpecialChild,
    CascadeSpecialParent,
    CascadeWR02Grandchild,
    CascadeWR02Root,
    CascadeWR02SharedChild,
)

pytestmark = pytest.mark.usefixtures("setup_fake_redis_for_cascade_apply")


async def _apply_cascade(fake_redis_client, root, cascade=True):
    return await arun_sha(
        fake_redis_client,
        type(root).Meta,
        CASCADE_TTL_APPLY_SCRIPT_NAME,
        1,
        root.key,
        type(root).__name__,
        SPECIAL_FIELD_KEY_PREFIX,
        type(root).Meta.ttl,
        1 if cascade else 0,
        CASCADE_PLAN_KEY,
    )


# --- Special-field-child gap closure ---


@pytest.mark.asyncio
async def test_cascade_apply_refreshes_special_field_child_keys_sanity(
    fake_redis_client,
):
    # Arrange
    # A saved child with BOTH special-field kinds actually populated,
    # so their Redis keys exist and can carry a TTL.
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()
    await fake_redis_client.persist(parent.key)
    await fake_redis_client.persist(child.key)

    # Act
    await _apply_cascade(fake_redis_client, parent)

    # Assert
    # Root's own key + the reached child's main key AND both of the
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


# --- ARGV[4] cascade gate ---


@pytest.mark.asyncio
async def test_cascade_apply_with_cascade_false_refreshes_only_root_main_and_special_keys(
    fake_redis_client,
):
    # Arrange
    # A saved parent -> child pair with the child's special fields
    # populated, so a wrongly-cascading call would have something to reach.
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()
    await fake_redis_client.persist(parent.key)
    await fake_redis_client.persist(child.key)
    # aadd/apush already auto-refresh the special-field keys' own TTL (via
    # refresh_ttl_if_needed), unrelated to the cascade call under test --
    # persist them too so a positive TTL after Act can only be explained by
    # a (wrongly) cascading call, not by that earlier auto-refresh.
    await fake_redis_client.persist(RedisSet.special_field_key(child.key, "tags"))
    await fake_redis_client.persist(
        RedisPriorityQueue.special_field_key(child.key, "scores")
    )

    # Act
    # ARGV[4]=0 (cascade=False): no edge is ever followed.
    await _apply_cascade(fake_redis_client, parent, cascade=False)

    # Assert
    # The root's own key (and its own special-field keys, of which
    # CascadeSpecialParent has none) is refreshed...
    assert await fake_redis_client.ttl(parent.key) > 0
    # ...but the FK-edged child (main key AND its own special-field keys)
    # is never reached.
    assert await fake_redis_client.ttl(child.key) in (-1, -2)
    assert await fake_redis_client.ttl(
        RedisSet.special_field_key(child.key, "tags")
    ) in (-1, -2)
    assert await fake_redis_client.ttl(
        RedisPriorityQueue.special_field_key(child.key, "scores")
    ) in (-1, -2)


@pytest.mark.asyncio
async def test_cascade_apply_with_cascade_false_still_refreshes_roots_own_special_keys(
    fake_redis_client,
):
    # Arrange
    # The root itself carries populated special fields; cascade=False must
    # still refresh those (they belong to the root, not a cascade-reached
    # child) even though no edge is followed.
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    await fake_redis_client.persist(child.key)

    # Act
    result = await _apply_cascade(fake_redis_client, child, cascade=False)

    # Assert
    # The root's own main key and its own special-field keys all refresh.
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
    # A leaf model has no outgoing edges either way, so the dangling counts
    # stay zero regardless of the cascade flag.
    assert result == [0, 0]


# --- Dangling-count contract ---


@pytest.mark.asyncio
async def test_cascade_apply_returns_zero_dangling_counts_when_everything_exists(
    fake_redis_client,
):
    # Arrange
    # Identical arrangement to the sanity test above — both special
    # fields on the reached child are actually populated, so nothing is
    # dangling.
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()
    await fake_redis_client.persist(parent.key)
    await fake_redis_client.persist(child.key)

    # Act
    result = await _apply_cascade(fake_redis_client, parent)

    # Assert
    # No dangling children, no dangling special keys.
    assert result == [0, 0]


@pytest.mark.asyncio
async def test_cascade_apply_counts_fully_dangling_child_and_its_special_keys(
    fake_redis_client,
):
    # Arrange
    # The referenced child key is never created — its main key AND
    # both of CascadeSpecialChild's special-field keys (tags, scores) are all
    # dangling.
    parent = await CascadeSpecialParent(
        child="CascadeSpecialChild:does-not-exist"
    ).asave()
    await fake_redis_client.persist(parent.key)

    # Act
    result = await _apply_cascade(fake_redis_client, parent)

    # Assert
    # One dangling main key, two dangling special keys.
    assert result == [1, 2]


@pytest.mark.asyncio
async def test_cascade_apply_counts_dangling_special_keys_on_an_existing_child(
    fake_redis_client,
):
    # Arrange
    # The child's main key exists but neither special field was ever
    # populated, so only its two special-field keys are dangling.
    child = await CascadeSpecialChild().asave()
    parent = await CascadeSpecialParent(child=child.key).asave()
    await fake_redis_client.persist(parent.key)
    await fake_redis_client.persist(child.key)

    # Act
    result = await _apply_cascade(fake_redis_client, parent)

    # Assert
    # Child main key present (not dangling), both special keys dangling.
    assert result == [0, 2]


# --- Shape-1/2/3 re-proof under the REAL script ---


@pytest.mark.asyncio
async def test_shape1_chain_root_reaches_the_expected_prefix_of_the_chain_sanity(
    fake_redis_client,
):
    # Arrange
    # CascadeChainRoot.head carries CascadeTTL(depth=2); a->b->c->d chain.
    # depth=2 is the child subtree's budget: root->a (fresh budget 2), a->b
    # (blanket, budget 1), b->c (blanket, budget 0), c->d (budget exhausted).
    # CascadeChainRoot.head carries an explicit depth=2 override (refreshes
    # child budget to 2), then CascadeChainNode.next is a blanket-decrementing
    # hop at each subsequent established step (root->a budget 2, a->b budget
    # 1, b->c budget 0, c->d exhausted -- d is never reached).
    d = await CascadeChainNode(name="d").asave()
    c = await CascadeChainNode(name="c", next=d.key).asave()
    b = await CascadeChainNode(name="b", next=c.key).asave()
    a = await CascadeChainNode(name="a", next=b.key).asave()
    root = await CascadeChainRoot(head=a.key).asave()
    all_keys = (root.key, a.key, b.key, c.key, d.key)
    for key in all_keys:
        await fake_redis_client.persist(key)

    # Act
    await _apply_cascade(fake_redis_client, root)

    # Assert
    # The Lua refresh set matches the hand-derived expected set —
    # root, a, b, c refreshed; d (beyond the depth-2 budget) left untouched.
    refreshed = {key for key in all_keys if await fake_redis_client.ttl(key) > 0}
    assert refreshed == {root.key, a.key, b.key, c.key}
    assert await fake_redis_client.ttl(d.key) in (-1, -2)


@pytest.mark.asyncio
async def test_depth0_shallow_root_extends_via_explicit_override_matches_hand_derived_expected_set(
    fake_redis_client,
):
    # Arrange
    # Regression. CascadeShallowRoot.entry carries CascadeTTL(depth=0)
    # — the value that used to compute `depth - 1 == -1 == UNBOUNDED` and turn the
    # whole subtree unbounded. CascadeExtendingNode.onward is an explicit depth=5
    # override that must REFRESH the budget and extend PAST the depth=0 entry,
    # not be silenced by it. The Lua must reach EXACTLY the hand-derived
    # expected set below for this scalar shape-1 chain (no shape-2 fakeredis
    # divergence).
    tail = await CascadeChainNode(name="tail").asave()
    head = await CascadeChainNode(name="head", next=tail.key).asave()
    extending = await CascadeExtendingNode(onward=head.key).asave()
    root = await CascadeShallowRoot(entry=extending.key).asave()
    all_keys = (root.key, extending.key, head.key, tail.key)
    for key in all_keys:
        await fake_redis_client.persist(key)

    # Act
    await _apply_cascade(fake_redis_client, root)

    # Assert
    # The depth=0 entry did extend the full chain via the explicit
    # override (all four keys), not by an unbounded walk of a mis-cast sentinel.
    refreshed = {key for key in all_keys if await fake_redis_client.ttl(key) > 0}
    assert refreshed == set(all_keys)


@pytest.mark.asyncio
async def test_independent_sibling_depth_budgets_match_hand_derived_expected_set(
    fake_redis_client,
):
    # Arrange
    # Regression on the blanket-decrement path (distinguishes the fixed Lua
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

    # Act
    await _apply_cascade(fake_redis_client, root)

    # Assert
    refreshed = {key for key in all_keys if await fake_redis_client.ttl(key) > 0}
    assert refreshed == {root.key, s1.key, s2.key, l1.key, l2.key, l3.key, l4.key}


@pytest.mark.asyncio
async def test_shape2_collection_of_fk_root_always_refreshes_sanity(
    fake_redis_client,
):
    # Arrange
    # CascadeBookCollection.co_authors carries CascadeTTL() (unbounded).
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
    # `push_edges`'s `edge.is_collection` branch (which requires a Lua *table*)
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

    # Act
    # Must not error despite the collection-shape read quirk above.
    await _apply_cascade(fake_redis_client, book)

    # Assert
    # The root itself is always fully refreshed regardless of the
    # fakeredis JSON.GET quirk documented above.
    assert await fake_redis_client.ttl(book.key) > 0


@pytest.mark.asyncio
async def test_shape3_nested_submodel_fk_reaches_the_targets_own_ttl_sanity(
    fake_redis_client,
):
    # Arrange
    # CascadeBookNested.profile is a nested submodel whose OWN field
    # (CascadeProfile.mentor) carries the cascade marker (zero-hop nesting).
    author = await CascadeAuthor(name="mentor").asave()
    profile = CascadeProfile(mentor=author.key)
    book = await CascadeBookNested(title="memoir", profile=profile).asave()
    await fake_redis_client.persist(author.key)
    await fake_redis_client.persist(book.key)

    # Act
    await _apply_cascade(fake_redis_client, book)

    # Assert
    # The outer holder (root) and the FK target reached through the
    # nested submodel are both refreshed; the nested submodel itself has no
    # key of its own (same RedisJSON document as book).
    assert await fake_redis_client.ttl(book.key) > 0
    assert await fake_redis_client.ttl(author.key) > 0


# --- Diamond dedup ---


@pytest.mark.asyncio
async def test_diamond_shared_child_refreshed_exactly_once_via_either_edge_sanity(
    fake_redis_client,
):
    # Arrange
    # CascadeDiamondRoot.left/right both point at the SAME child.
    child = await CascadeDiamondChild(name="shared").asave()
    root = await CascadeDiamondRoot(left=child.key, right=child.key).asave()
    await fake_redis_client.persist(child.key)
    await fake_redis_client.persist(root.key)

    # Act
    # Must not error from the double-visit (visited-set dedup).
    await _apply_cascade(fake_redis_client, root)

    # Assert
    assert await fake_redis_client.ttl(root.key) > 0
    assert await fake_redis_client.ttl(child.key) > 0


# --- Self-reference cycle safety ---


@pytest.mark.asyncio
async def test_self_reference_cycle_does_not_error_or_infinite_loop_sanity(
    fake_redis_client,
):
    # Arrange
    # a -> b -> a (cycle).
    a = await CascadeChainNode(name="a").asave()
    b = await CascadeChainNode(name="b", next=a.key).asave()
    a.next = b.key
    await a.asave()
    await fake_redis_client.persist(a.key)
    await fake_redis_client.persist(b.key)

    # Act
    # Bounded by the visited-set; must complete without hanging/erroring.
    await _apply_cascade(fake_redis_client, a)

    # Assert
    assert await fake_redis_client.ttl(a.key) > 0
    assert await fake_redis_client.ttl(b.key) > 0


# --- Genuine self-loop + shared-child-via-two-independent-roots ---


@pytest.mark.asyncio
async def test_genuine_single_node_self_loop_does_not_hang_or_error_sanity(
    fake_redis_client,
):
    # Arrange
    # A genuine single-node self-loop (distinct from the two-node
    # a<->b cycle above) -- node.next set to its OWN key after an initial
    # save, then re-saved.
    node = await CascadeChainNode(name="solo").asave()
    node.next = node.key
    await node.asave()
    await fake_redis_client.persist(node.key)

    # Act
    # Bounded by the visited-set; must complete without hanging/erroring.
    await _apply_cascade(fake_redis_client, node)

    # Assert
    assert await fake_redis_client.ttl(node.key) > 0


@pytest.mark.asyncio
async def test_shared_child_via_two_independent_roots_refreshed_from_either_root_sanity(
    fake_redis_client,
):
    # Arrange
    # TWO separately-saved CascadeSpecialParent instances that both
    # point their child field at the SAME saved CascadeSpecialChild instance
    # -- distinct from test_diamond_shared_child_refreshed_exactly_once_via_either_edge_sanity
    # above, which uses a SINGLE root with two fields, not two independent
    # roots.
    child = await CascadeSpecialChild().asave()
    root_a = await CascadeSpecialParent(child=child.key).asave()
    root_b = await CascadeSpecialParent(child=child.key).asave()
    for key in (child.key, root_a.key, root_b.key):
        await fake_redis_client.persist(key)

    # Act
    # Apply cascade from EACH root independently.
    await _apply_cascade(fake_redis_client, root_a)
    assert await fake_redis_client.ttl(root_a.key) > 0
    assert await fake_redis_client.ttl(child.key) > 0

    await fake_redis_client.persist(child.key)
    await _apply_cascade(fake_redis_client, root_b)

    # Assert
    # The shared child refreshes from either independent root.
    assert await fake_redis_client.ttl(root_b.key) > 0
    assert await fake_redis_client.ttl(child.key) > 0


# --- Diamond with differing per-path depth budgets ---


@pytest.mark.asyncio
async def test_shared_child_own_key_always_refreshed_regardless_of_visit_order_sanity(
    fake_redis_client,
):
    # Arrange
    # deep_path/shallow_path both point at the SAME saved
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

    # Assert
    # The shared child's OWN key always has a positive TTL,
    # unconditionally, regardless of which sibling edge the DFS visits first
    # (accepted, order-dependent-but-documented semantics apply only
    # to the child's OWN deeper descendants, not to the child itself).
    assert await fake_redis_client.ttl(root.key) > 0
    assert await fake_redis_client.ttl(shared_child.key) > 0

    # The grandchild is reached deterministically via CascadeWR02SharedChild.next,
    # an explicit per-field CascadeTTL() override edge: next_hop's
    # edge.resets_depth_budget branch fires before any remaining_budget
    # inspection, so the grandchild is ALWAYS refreshed regardless of which
    # sibling edge (deep_path budget=5 or
    # shallow_path budget=1) the DFS visits first — this fixture's downstream
    # edge cannot demonstrate order-dependence either way (see
    # test_max_budget_wins_shared_child_reaches_deep_paths_full_prefix_regardless_of_visit_order_sanity
    # below for the actual regression, which uses a genuinely
    # budget-decrementing blanket edge instead).
    assert await fake_redis_client.ttl(grandchild.key) > 0


@pytest.mark.asyncio
async def test_max_budget_wins_shared_child_reaches_deep_paths_full_prefix_regardless_of_visit_order_sanity(
    fake_redis_client,
):
    # Arrange
    # CascadeMaxBudgetRoot.deep_path/shallow_path both point at the
    # SAME saved CascadeChainNode head ("shared"), with differing finite depth
    # budgets (4 vs 1). Unlike CascadeWR02SharedChild.next (an override edge),
    # CascadeChainNode.next is a BLANKET (non-override) edge that genuinely
    # decrements a real remaining_budget on every established hop, so the two
    # differing budgets are actually distinguishable. A 4-node
    # chain sits behind the shared head: shared -> c1 -> c2 -> c3 -> c4.
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
        await fake_redis_client.persist(key)

    # Act
    await _apply_cascade(fake_redis_client, root)

    # Assert
    # The full reach the LARGER (depth=4) budget grants is refreshed —
    # root, shared, c1, c2, c3, c4 — deterministically, regardless of which of
    # the two root fields the Lua DFS processes/pops first. Under the old
    # first-processed-wins bug, this set would be order-dependent (sometimes
    # only reaching c1 via the depth=1 shallow_path frame).
    refreshed = {key for key in all_keys if await fake_redis_client.ttl(key) > 0}
    assert refreshed == set(all_keys)


# --- Ported from the deleted client-side-planner unit tests (blanket opt-out + nested-submodel budget) ---


@pytest.mark.asyncio
async def test_blanket_opt_out_field_stops_traversal_despite_blanket_global(
    fake_redis_client,
):
    # Arrange
    # CascadeBlanketOptOut.child carries an explicit
    # CascadeTTL(enabled=False), overriding an otherwise-blanket-enabled
    # Meta.cascade_ttl(depth=2) — the explicit per-field opt-out wins.
    leaf = await CascadeBlanketLeaf(name="leaf").asave()
    root = await CascadeBlanketOptOut(child=leaf.key).asave()
    await fake_redis_client.persist(root.key)
    await fake_redis_client.persist(leaf.key)

    # Act
    await _apply_cascade(fake_redis_client, root)

    # Assert
    # Root refreshed, leaf never reached.
    assert await fake_redis_client.ttl(root.key) > 0
    assert await fake_redis_client.ttl(leaf.key) in (-1, -2)


@pytest.mark.asyncio
async def test_nested_submodel_zero_hop_does_not_consume_depth_budget(
    fake_redis_client,
):
    # Arrange
    # Budget-non-consumption contract, ported from the
    # deleted test_nested_submodel_hop_does_not_consume_the_depth_budget
    # planner unit test. CascadeNestedDepthRoot.holder carries an explicit
    # depth=1; the zero-hop walk through .profile (a nested inline submodel,
    # shape 3) must not consume that budget before the real FK hop into
    # .mentor (which is reached via CascadeBlanketNestedProfile's own
    # blanket-enabled Meta.cascade_ttl(depth=2)).
    mentor = await CascadeBlanketLeaf(name="mentor").asave()
    holder = await CascadeBlanketNestedHolder(
        profile=CascadeBlanketNestedProfile(mentor=mentor.key)
    ).asave()
    root = await CascadeNestedDepthRoot(holder=holder.key).asave()
    await fake_redis_client.persist(root.key)
    await fake_redis_client.persist(holder.key)
    await fake_redis_client.persist(mentor.key)

    # Act
    await _apply_cascade(fake_redis_client, root)

    # Assert
    # Reached despite only a depth=1 budget on the outer field —
    # proving the zero-hop `profile` field never decremented the depth=1
    # budget inherited by `holder`, so the real FK hop into `mentor` still
    # saw the untouched budget and was followed.
    refreshed = {
        key
        for key in (root.key, holder.key, mentor.key)
        if await fake_redis_client.ttl(key) > 0
    }
    assert refreshed == {root.key, holder.key, mentor.key}


@pytest.mark.asyncio
async def test_node_beyond_nested_depth_budget_is_never_reached_sanity(
    fake_redis_client,
):
    # Arrange
    # Extends the sibling zero-hop test one hop further via
    # CascadeBlanketLeaf.onward. Budget arithmetic: root's depth=1 override
    # enters holder at budget=1; the zero-hop .profile field doesn't consume
    # it; the real hop into .mentor (via CascadeBlanketNestedProfile's own
    # blanket depth=2) decrements 1->0; mentor's own blanket onward edge is
    # therefore evaluated at budget=0 and never followed.
    beyond = await CascadeBlanketLeaf(name="beyond").asave()
    mentor = await CascadeBlanketLeaf(name="mentor", onward=beyond.key).asave()
    holder = await CascadeBlanketNestedHolder(
        profile=CascadeBlanketNestedProfile(mentor=mentor.key)
    ).asave()
    root = await CascadeNestedDepthRoot(holder=holder.key).asave()
    await fake_redis_client.persist(root.key)
    await fake_redis_client.persist(holder.key)
    await fake_redis_client.persist(mentor.key)
    await fake_redis_client.persist(beyond.key)

    # Act
    await _apply_cascade(fake_redis_client, root)

    # Assert
    refreshed = {
        key
        for key in (root.key, holder.key, mentor.key)
        if await fake_redis_client.ttl(key) > 0
    }
    assert refreshed == {root.key, holder.key, mentor.key}
    assert await fake_redis_client.ttl(beyond.key) in (-1, -2)


# --- Missing-plan-key degrade path ---


@pytest.mark.asyncio
async def test_cascade_apply_with_deleted_plan_key_degrades_to_root_only(
    fake_redis_client,
):
    # Arrange
    # The plan key is deleted, so the Lua's GET returns nil -> `or {}` empty
    # plan. A cascade call must not raise and must still refresh the root's own
    # main key; the FK child is unreachable with no plan entry.
    child = await CascadeSpecialChild().asave()
    parent = await CascadeSpecialParent(child=child.key).asave()
    await fake_redis_client.persist(parent.key)
    await fake_redis_client.persist(child.key)
    await fake_redis_client.delete(CASCADE_PLAN_KEY)

    # Act
    await _apply_cascade(fake_redis_client, parent)

    # Assert
    assert await fake_redis_client.ttl(parent.key) > 0
    assert await fake_redis_client.ttl(child.key) in (-1, -2)
