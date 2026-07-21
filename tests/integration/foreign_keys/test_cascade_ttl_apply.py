import pytest

from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeAuthor,
    CascadeBookCollection,
    CascadeChainRoot,
    CascadeDictCollectionRoot,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

ROOT_TTL_SECONDS = 120

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


# --- Confirmatory dual-backend parity ---


@pytest.mark.asyncio
async def test_cascade_apply_refreshes_special_field_child_keys_sanity(
    real_redis_client,
):
    # Arrange
    # Identical scenario/assertions to the fakeredis version in
    # tests/unit/cascade/test_cascade_apply_lua.py — proving JSON.GET
    # output-shape parity for this scenario by construction, not by comment.
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()
    await real_redis_client.persist(parent.key)
    await real_redis_client.persist(child.key)

    # Act
    await _apply_cascade(real_redis_client, parent)

    # Assert
    assert await real_redis_client.ttl(parent.key) > 0
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


@pytest.mark.asyncio
async def test_cascade_apply_refreshes_every_collection_of_fk_element_sanity(
    real_redis_client,
):
    # Arrange
    # On REAL Redis, JSON.GET's single-path response for an array-valued
    # match is correctly double-wrapped (verified directly against Redis
    # Stack), so this shape-2 scenario refreshes every element — unlike the
    # documented fakeredis divergence in
    # tests/unit/cascade/test_cascade_apply_lua.py::test_shape2_collection_of_fk_root_always_refreshes_sanity.
    author_a = await CascadeAuthor(name="a").asave()
    author_b = await CascadeAuthor(name="b").asave()
    book = await CascadeBookCollection(
        title="anthology", co_authors=[author_a.key, author_b.key]
    ).asave()
    for key in (author_a.key, author_b.key, book.key):
        await real_redis_client.persist(key)

    # Act
    await _apply_cascade(real_redis_client, book)

    # Assert
    assert await real_redis_client.ttl(book.key) > 0
    assert await real_redis_client.ttl(author_a.key) > 0
    assert await real_redis_client.ttl(author_b.key) > 0


@pytest.mark.asyncio
async def test_cascade_apply_refreshes_every_dict_value_fk_element_sanity(
    real_redis_client,
):
    # Arrange
    # Dict-value counterpart of the list-based test above -- proves JSON.GET's
    # pairs()-based element iteration in push_edges works identically for a
    # JSON-object-shaped match as for a JSON-array one.
    author_a = await CascadeAuthor(name="a").asave()
    author_b = await CascadeAuthor(name="b").asave()
    book = await CascadeDictCollectionRoot(
        title="anthology", co_authors={"a": author_a.key, "b": author_b.key}
    ).asave()
    for key in (author_a.key, author_b.key, book.key):
        await real_redis_client.persist(key)

    # Act
    await _apply_cascade(real_redis_client, book)

    # Assert
    assert await real_redis_client.ttl(book.key) > 0
    assert await real_redis_client.ttl(author_a.key) > 0
    assert await real_redis_client.ttl(author_b.key) > 0


@pytest.mark.asyncio
async def test_cascade_apply_skips_corrupt_wrongtype_reached_target_sanity(
    real_redis_client,
):
    # Arrange
    # This is the SOLE regression guard for the WRONGTYPE-degradation fix in
    # library.lua::read_reference_paths -- fakeredis's JSON.GET does not emulate
    # WRONGTYPE (see CONCERNS.md), so only real Redis Stack can prove this.
    await real_redis_client.set("CascadeChainNode:corrupt", "garbage")
    root = await CascadeChainRoot(head="CascadeChainNode:corrupt").asave()
    await real_redis_client.persist(root.key)
    await real_redis_client.persist("CascadeChainNode:corrupt")

    # Act - before the Lua fix this raises (RED); after the fix it must not (GREEN)
    await _apply_cascade(real_redis_client, root)

    # Assert
    assert await real_redis_client.ttl(root.key) > 0
    assert await real_redis_client.ttl("CascadeChainNode:corrupt") > 0


@pytest.mark.asyncio
async def test_baked_plan_refreshes_whole_reachable_subtree_with_root_child_split(
    real_redis_client,
):
    # Arrange
    # No TTL on the child or its special keys before the action -- only the
    # baked cascade plan can bring the whole reachable subtree back to life.
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()
    tags_key = RedisSet.special_field_key(child.key, "tags")
    scores_key = RedisPriorityQueue.special_field_key(child.key, "scores")
    for key in (parent.key, child.key, tags_key, scores_key):
        await real_redis_client.persist(key)

    # Act
    # A distinct root ttl so the assertion proves the root-vs-child split.
    await real_redis_client.fcall(
        parent.Meta.cascade_function_name,
        1,
        parent.key,
        type(parent).__name__,
        SPECIAL_FIELD_KEY_PREFIX,
        ROOT_TTL_SECONDS,
        1,
    )

    # Assert
    # The root honors the caller-supplied root ttl...
    parent_ttl = await real_redis_client.ttl(parent.key)
    assert 0 < parent_ttl <= ROOT_TTL_SECONDS
    # ...while every reachable child key (main + special) refreshes to the
    # child's OWN Meta.ttl, strictly above the root ttl.
    for key in (child.key, tags_key, scores_key):
        child_ttl = await real_redis_client.ttl(key)
        assert ROOT_TTL_SECONDS < child_ttl <= CASCADE_FIXTURE_TTL_SECONDS
