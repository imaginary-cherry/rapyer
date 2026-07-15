import pytest

from rapyer.scripts import arun_sha
from rapyer.scripts.constants import CASCADE_TTL_APPLY_SCRIPT_NAME
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBookCollection,
    CascadeDictCollectionRoot,
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


# NOTE: the pipelined `aset_ttl`/`refresh_ttl` cascade branches (enqueuing
# `run_sha` into a pipeline via `ensure_pipeline`/`pipeline_with_execution`)
# do NOT self-heal a NOSCRIPT -- that recovery was scoped back out of the
# generic pipeline helpers in favor of keeping it local to `_apipeline`
# (general model writes). Extending the same recovery to these TTL-refresh
# paths is tracked as a follow-up; see NOSCRIPT-ISSUE.md.
