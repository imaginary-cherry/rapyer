import pytest

from rapyer.scripts import arun_sha
from rapyer.scripts.constants import CASCADE_TTL_APPLY_SCRIPT_NAME
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import (
    CascadeChainNode,
    CascadeChainRoot,
    CascadeDiamondChild,
    CascadeDiamondRoot,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")


async def _apply_cascade(real_redis_client, root):
    return await arun_sha(
        real_redis_client,
        type(root).Meta,
        CASCADE_TTL_APPLY_SCRIPT_NAME,
        1,
        root.key,
        type(root).__name__,
        SPECIAL_FIELD_KEY_PREFIX,
        type(root).Meta.ttl,
    )


# --- (a) Multi-level chain ---


@pytest.mark.asyncio
async def test_multi_level_chain_reaches_expected_prefix_sanity(real_redis_client):
    """
    This test mirrors tests/unit/cascade/test_cascade_apply_lua.py::
    test_shape1_chain_root_reaches_the_expected_prefix_of_the_chain_sanity --
    identical scenario/assertions, proving JSON.GET output-shape parity for
    this scenario by construction, not by comment.
    """
    d = await CascadeChainNode(name="d").asave()
    c = await CascadeChainNode(name="c", next=d.key).asave()
    b = await CascadeChainNode(name="b", next=c.key).asave()
    a = await CascadeChainNode(name="a", next=b.key).asave()
    root = await CascadeChainRoot(head=a.key).asave()
    all_keys = (root.key, a.key, b.key, c.key, d.key)
    for key in all_keys:
        await real_redis_client.persist(key)

    # Act
    await _apply_cascade(real_redis_client, root)

    # Assert: root, a, b, c refreshed; d (beyond the depth-2 budget) untouched.
    refreshed = {key for key in all_keys if await real_redis_client.ttl(key) > 0}
    assert refreshed == {root.key, a.key, b.key, c.key}
    assert await real_redis_client.ttl(d.key) in (-1, -2)


# --- (b) Cyclic ---


@pytest.mark.asyncio
async def test_cyclic_two_node_cycle_does_not_hang_or_error_sanity(real_redis_client):
    """
    This test mirrors tests/unit/cascade/test_cascade_apply_lua.py::
    test_self_reference_cycle_does_not_error_or_infinite_loop_sanity --
    identical scenario/assertions, proving JSON.GET output-shape parity for
    this scenario by construction, not by comment.
    """
    a = await CascadeChainNode(name="a").asave()
    b = await CascadeChainNode(name="b", next=a.key).asave()
    a.next = b.key
    await a.asave()
    await real_redis_client.persist(a.key)
    await real_redis_client.persist(b.key)

    # Act: bounded by the visited-set; must complete without hanging/erroring.
    await _apply_cascade(real_redis_client, a)

    # Assert
    assert await real_redis_client.ttl(a.key) > 0
    assert await real_redis_client.ttl(b.key) > 0


# --- (c) Self-reference (genuine single-node self-loop) ---


@pytest.mark.asyncio
async def test_genuine_single_node_self_loop_does_not_hang_or_error_sanity(
    real_redis_client,
):
    """
    This test mirrors this plan's Task 1 fakeredis addition
    (tests/unit/cascade/test_cascade_apply_lua.py::
    test_genuine_single_node_self_loop_does_not_hang_or_error_sanity) --
    identical scenario/assertions, proving JSON.GET output-shape parity for
    this scenario by construction, not by comment.
    """
    node = await CascadeChainNode(name="solo").asave()
    node.next = node.key
    await node.asave()
    await real_redis_client.persist(node.key)

    # Act: bounded by the visited-set; must complete without hanging/erroring.
    await _apply_cascade(real_redis_client, node)

    # Assert
    assert await real_redis_client.ttl(node.key) > 0


# --- (d) Diamond dedup ---


@pytest.mark.asyncio
async def test_diamond_shared_child_refreshed_exactly_once_via_either_edge_sanity(
    real_redis_client,
):
    """
    This test mirrors tests/unit/cascade/test_cascade_apply_lua.py::
    test_diamond_shared_child_refreshed_exactly_once_via_either_edge_sanity --
    identical scenario/assertions, proving JSON.GET output-shape parity for
    this scenario by construction, not by comment.
    """
    child = await CascadeDiamondChild(name="shared").asave()
    root = await CascadeDiamondRoot(left=child.key, right=child.key).asave()
    await real_redis_client.persist(child.key)
    await real_redis_client.persist(root.key)

    # Act: must not error from the double-visit (visited-set dedup).
    await _apply_cascade(real_redis_client, root)

    # Assert
    assert await real_redis_client.ttl(root.key) > 0
    assert await real_redis_client.ttl(child.key) > 0


# --- (e) Shared-child via two independent roots ---


@pytest.mark.asyncio
async def test_shared_child_via_two_independent_roots_refreshed_from_either_root_sanity(
    real_redis_client,
):
    """
    This test mirrors this plan's Task 1 fakeredis addition
    (tests/unit/cascade/test_cascade_apply_lua.py::
    test_shared_child_via_two_independent_roots_refreshed_from_either_root_sanity) --
    identical scenario/assertions, proving JSON.GET output-shape parity for
    this scenario by construction, not by comment.
    """
    child = await CascadeSpecialChild().asave()
    root_a = await CascadeSpecialParent(child=child.key).asave()
    root_b = await CascadeSpecialParent(child=child.key).asave()
    for key in (child.key, root_a.key, root_b.key):
        await real_redis_client.persist(key)

    # Act: apply cascade from EACH root independently.
    await _apply_cascade(real_redis_client, root_a)
    assert await real_redis_client.ttl(root_a.key) > 0
    assert await real_redis_client.ttl(child.key) > 0

    await real_redis_client.persist(child.key)
    await _apply_cascade(real_redis_client, root_b)

    # Assert: the shared child refreshes from either independent root.
    assert await real_redis_client.ttl(root_b.key) > 0
    assert await real_redis_client.ttl(child.key) > 0
