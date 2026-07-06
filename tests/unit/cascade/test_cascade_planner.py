import pytest

from rapyer.cascade import CascadePlanner
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBlanketLeaf,
    CascadeBlanketOptOut,
    CascadeBlanketRoot,
    CascadeBookDirect,
    CascadeChainNode,
    CascadeChainRoot,
    CascadeDiamondChild,
    CascadeDiamondRoot,
    CascadeExtendingNode,
    CascadeMultiDepthRoot,
    CascadeShallowRoot,
)

pytestmark = pytest.mark.usefixtures("setup_fake_redis_for_cascade_models")


# --- Single hop / basic shape-1 coverage ---


@pytest.mark.asyncio
async def test_single_hop_reaches_direct_child():
    # Arrange
    child = await CascadeChainNode(name="child").asave()
    root = await CascadeChainNode(name="root", next=child.key).asave()

    # Act
    result = await CascadePlanner().atraverse(root.key, CascadeChainNode)

    # Assert
    assert result == [root.key, child.key]


@pytest.mark.asyncio
async def test_disabled_field_spec_stops_traversal():
    # Arrange: CascadeBookDirect.author carries CascadeTTL(enabled=False)
    author = await CascadeAuthor(name="alice").asave()
    book = await CascadeBookDirect(title="x", author=author.key).asave()

    # Act
    result = await CascadePlanner().atraverse(book.key, CascadeBookDirect)

    # Assert
    assert result == [book.key]


# --- D-04: unbounded default depth ---


@pytest.mark.asyncio
async def test_unbounded_default_depth_traverses_full_chain():
    # Arrange: 4-node chain, no depth cap anywhere (bare blanket Meta.cascade_ttl)
    d = await CascadeChainNode(name="d").asave()
    c = await CascadeChainNode(name="c", next=d.key).asave()
    b = await CascadeChainNode(name="b", next=c.key).asave()
    a = await CascadeChainNode(name="a", next=b.key).asave()

    # Act
    result = await CascadePlanner().atraverse(a.key, CascadeChainNode)

    # Assert
    assert result == [a.key, b.key, c.key, d.key]


# --- D-03 revised / D-05: per-subtree depth budget capped via an explicit field ---


@pytest.mark.asyncio
async def test_multi_hop_chain_truncated_by_field_depth():
    # Arrange: CascadeChainRoot.head carries CascadeTTL(depth=2); A->B->C->D chain.
    d = await CascadeChainNode(name="d").asave()
    c = await CascadeChainNode(name="c", next=d.key).asave()
    b = await CascadeChainNode(name="b", next=c.key).asave()
    a = await CascadeChainNode(name="a", next=b.key).asave()
    root = await CascadeChainRoot(head=a.key).asave()

    # Act
    result = await CascadePlanner().atraverse(root.key, CascadeChainRoot)

    # Assert
    assert result == [root.key, a.key, b.key, c.key]
    assert d.key not in result


# --- CASC-04: cycle safety ---


@pytest.mark.asyncio
async def test_self_reference_cycle_terminates_without_double_collecting_root():
    # Arrange: A -> B -> A
    a = await CascadeChainNode(name="a").asave()
    b = await CascadeChainNode(name="b", next=a.key).asave()
    a.next = b.key
    await a.asave()

    # Act
    result = await CascadePlanner().atraverse(a.key, CascadeChainNode)

    # Assert
    assert result.count(a.key) == 1
    assert result.count(b.key) == 1
    assert set(result) == {a.key, b.key}


# --- CASC-04: dangling / missing child ---


@pytest.mark.asyncio
async def test_dangling_child_stops_recursion_without_raising():
    # Arrange: root's next points at a key that was never saved.
    root = await CascadeChainNode(
        name="root", next="CascadeChainNode:does-not-exist"
    ).asave()

    # Act
    result = await CascadePlanner().atraverse(root.key, CascadeChainNode)

    # Assert
    assert result == [root.key]
    assert "CascadeChainNode:does-not-exist" not in result


# --- D-05: diamond de-duplication ---


@pytest.mark.asyncio
async def test_diamond_graph_deduplicates_shared_child():
    # Arrange
    child = await CascadeDiamondChild(name="shared").asave()
    root = await CascadeDiamondRoot(left=child.key, right=child.key).asave()

    # Act
    result = await CascadePlanner().atraverse(root.key, CascadeDiamondRoot)

    # Assert
    assert result.count(child.key) == 1
    assert set(result) == {root.key, child.key}


# --- D-11: independent per-sibling-field ceilings ---


@pytest.mark.asyncio
async def test_multi_depth_root_siblings_reach_independently():
    # Arrange: two SEPARATE chains so the shared visited-set never interferes.
    s4 = await CascadeChainNode(name="s4").asave()
    s3 = await CascadeChainNode(name="s3", next=s4.key).asave()
    s2 = await CascadeChainNode(name="s2", next=s3.key).asave()
    s1 = await CascadeChainNode(name="s1", next=s2.key).asave()

    l4 = await CascadeChainNode(name="l4").asave()
    l3 = await CascadeChainNode(name="l3", next=l4.key).asave()
    l2 = await CascadeChainNode(name="l2", next=l3.key).asave()
    l1 = await CascadeChainNode(name="l1", next=l2.key).asave()

    root = await CascadeMultiDepthRoot(short_reach=s1.key, long_reach=l1.key).asave()

    # Act
    result = await CascadePlanner().atraverse(root.key, CascadeMultiDepthRoot)

    # Assert: short_reach (depth=1) reaches s1, s2 but not s3/s4.
    assert s1.key in result
    assert s2.key in result
    assert s3.key not in result
    assert s4.key not in result
    # Assert: long_reach (depth=3) reaches the entire 4-node chain.
    assert l1.key in result
    assert l2.key in result
    assert l3.key in result
    assert l4.key in result


# --- D-03 revised: a deeper field's explicit depth extends past a shallower ancestor ---


@pytest.mark.asyncio
async def test_deeper_field_extends_past_shallower_ancestor_budget():
    # Arrange: CascadeShallowRoot.entry has depth=0 (near-exhausted on entry);
    # CascadeExtendingNode.onward has its own explicit depth=5, which must
    # win regardless of the incoming (exhausted) budget.
    tail = await CascadeChainNode(name="tail").asave()
    head = await CascadeChainNode(name="head", next=tail.key).asave()
    extending = await CascadeExtendingNode(onward=head.key).asave()
    root = await CascadeShallowRoot(entry=extending.key).asave()

    # Act
    result = await CascadePlanner().atraverse(root.key, CascadeShallowRoot)

    # Assert: extending node reached despite depth=0 entry, and its own
    # explicit depth=5 lets traversal continue into the chain beyond it.
    assert extending.key in result
    assert head.key in result
    assert tail.key in result


# --- D-01/D-02/D-07 (shape 1 only in this task): blanket global enable ---


@pytest.mark.asyncio
async def test_blanket_global_enable_reaches_unannotated_direct_fk():
    # Arrange: CascadeBlanketRoot.child is unannotated; Meta.cascade_ttl is blanket-enabled.
    leaf = await CascadeBlanketLeaf(name="leaf").asave()
    root = await CascadeBlanketRoot(child=leaf.key).asave()

    # Act
    result = await CascadePlanner().atraverse(root.key, CascadeBlanketRoot)

    # Assert
    assert result == [root.key, leaf.key]


@pytest.mark.asyncio
async def test_field_opt_out_blocks_traversal_under_blanket_global():
    # Arrange: CascadeBlanketOptOut.child explicitly opts out (enabled=False).
    leaf = await CascadeBlanketLeaf(name="leaf").asave()
    root = await CascadeBlanketOptOut(child=leaf.key).asave()

    # Act
    result = await CascadePlanner().atraverse(root.key, CascadeBlanketOptOut)

    # Assert
    assert result == [root.key]
