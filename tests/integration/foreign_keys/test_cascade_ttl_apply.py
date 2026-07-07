import pytest

from rapyer.errors import PersistentNoScriptError
from rapyer.scripts import arun_sha
from rapyer.scripts.constants import CASCADE_TTL_APPLY_SCRIPT_NAME
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBookCollection,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")


async def _apply_cascade(real_redis_client, root) -> None:
    await arun_sha(
        real_redis_client,
        type(root).Meta,
        CASCADE_TTL_APPLY_SCRIPT_NAME,
        1,
        root.key,
        type(root).__name__,
        SPECIAL_FIELD_KEY_PREFIX,
    )


# --- Confirmatory dual-backend parity (D-05 / the retired ROADMAP 02-01 spike) ---


@pytest.mark.asyncio
async def test_cascade_apply_refreshes_special_field_child_keys_sanity(
    real_redis_client,
):
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


# --- ROADMAP criterion #5: survives SCRIPT FLUSH via NOSCRIPT self-heal ---


@pytest.mark.asyncio
async def test_cascade_apply_survives_script_flush_via_noscript_self_heal_sanity(
    flush_scripts,
    real_redis_client,
):
    # Arrange: register once (via setup_real_redis_for_cascade_apply,
    # requested indirectly through pytestmark's usefixtures), then flush the
    # server-side script cache — flush_scripts runs AFTER that initial
    # registration, so it wipes the already-loaded cascade SHA, forcing the
    # NOSCRIPT path on the arun_sha call below.
    child = await CascadeSpecialChild().asave()
    parent = await CascadeSpecialParent(child=child.key).asave()
    await real_redis_client.persist(parent.key)
    await real_redis_client.persist(child.key)

    # Act & Assert: no PersistentNoScriptError — arun_sha's NOSCRIPT self-heal
    # (handle_noscript_error -> register_scripts -> retry) covers this script
    # exactly like every other registered script.
    try:
        await _apply_cascade(real_redis_client, parent)
    except PersistentNoScriptError:
        pytest.fail(
            "cascade_ttl_apply did not survive SCRIPT FLUSH via NOSCRIPT self-heal"
        )

    assert await real_redis_client.ttl(parent.key) > 0
    assert await real_redis_client.ttl(child.key) > 0
