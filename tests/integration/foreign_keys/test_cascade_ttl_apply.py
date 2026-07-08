import pytest
import pytest_asyncio

from rapyer.cascade.planner import build_cascade_plan
from rapyer.errors import PersistentNoScriptError
from rapyer.result import CascadeResult
from rapyer.scripts import arun_sha
from rapyer.scripts.constants import CASCADE_TTL_APPLY_SCRIPT_NAME
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.integration.foreign_keys.conftest import CASCADE_INTEGRATION_MODELS
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBookCollection,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")

# Deliberately different from CascadeSpecialParent/Child's shared
# CASCADE_FIXTURE_TTL_SECONDS so a passing assertion proves the caller's
# explicit root ttl was actually applied (D-02), not a coincidental match.
SCRIPT_FLUSH_ROOT_TTL_SECONDS = 120


@pytest_asyncio.fixture
async def cascade_action_boundary_after_script_flush(
    setup_real_redis_for_cascade_apply, real_redis_client
):
    """
    WR-01: stashes ``_has_cascade`` (the exact D-05 mechanism ``init_rapyer()``
    uses) on top of the already-registered real-Redis wiring from
    ``setup_real_redis_for_cascade_apply``, THEN flushes the server-side
    script cache -- explicit, unambiguous ordering (no reliance on
    usefixtures-vs-parameter instantiation order) so the wired
    ``refresh_ttl``/``aset_ttl`` cascade branches (not the standalone
    ``arun_sha`` helper) are the ones forced onto the NOSCRIPT path.
    """
    plan = build_cascade_plan(CASCADE_INTEGRATION_MODELS)
    for model in CASCADE_INTEGRATION_MODELS:
        model._has_cascade = bool(plan[model.__name__].fks)
    await real_redis_client.execute_command("SCRIPT", "FLUSH")
    try:
        yield
    finally:
        for model in CASCADE_INTEGRATION_MODELS:
            model._has_cascade = False


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
#
# WR-01: the two tests below replace the previous
# `test_cascade_apply_survives_script_flush_via_noscript_self_heal_sanity`,
# which only drove `arun_sha` through the standalone `_apply_cascade` helper
# -- the ALREADY-self-healing standalone path (rapyer/scripts/registry.py's
# `arun_sha`). That gave false confidence: the actually-SHIPPED production
# surface is `aset_ttl`/`refresh_ttl` enqueuing `run_sha` into a pipeline via
# `ensure_pipeline`/`pipeline_with_execution`, a different code path that,
# before this fix, had zero NOSCRIPT handling. These tests drive that real
# surface directly.


@pytest.mark.asyncio
async def test_aset_ttl_cascade_survives_script_flush_via_shipped_run_sha_path_sanity(
    cascade_action_boundary_after_script_flush,
    real_redis_client,
):
    # Arrange: a healthy parent -> child pair (child's special fields
    # populated so dangling_special has a real zero to prove, not a
    # trivially-empty one), saved AFTER the script cache was flushed
    # (fixture ordering), so the very first cascade EVALSHA this test
    # issues is guaranteed to hit NOSCRIPT.
    child = await CascadeSpecialChild().asave()
    await child.tags.aadd("x")
    await child.scores.apush(1.0, priority=1.0)
    parent = await CascadeSpecialParent(child=child.key).asave()

    # Act & Assert: the opt-in `aset_ttl(cascade=True)` path -- must not
    # raise NoScriptError/PersistentNoScriptError, and must still return a
    # decoded CascadeResult (proving the retry path preserves the return
    # value, not just "didn't crash").
    try:
        result = await parent.aset_ttl(SCRIPT_FLUSH_ROOT_TTL_SECONDS, cascade=True)
    except PersistentNoScriptError:
        pytest.fail(
            "aset_ttl(cascade=True) did not survive SCRIPT FLUSH via the "
            "shipped run_sha-into-pipeline NOSCRIPT self-heal"
        )

    assert isinstance(result, CascadeResult)
    assert result.dangling_children == 0
    assert result.dangling_special == 0
    assert await real_redis_client.ttl(parent.key) > 0
    assert await real_redis_client.ttl(child.key) > 0


@pytest.mark.asyncio
async def test_asave_auto_cascade_survives_script_flush_via_shipped_run_sha_path_sanity(
    cascade_action_boundary_after_script_flush,
    real_redis_client,
):
    # Arrange: a healthy parent -> child pair, saved AFTER the script cache
    # was flushed, so refresh_ttl's automatic cascade branch (riding
    # flush_action_targets' ensure_pipeline inside a plain asave()) is the
    # first caller to hit the flushed cascade SHA.
    child = await CascadeSpecialChild().asave()
    parent = await CascadeSpecialParent(child=child.key).asave()
    await real_redis_client.persist(parent.key)
    await real_redis_client.persist(child.key)

    # Act & Assert: an ordinary write with no explicit ttl/cascade call
    # anywhere (D-04's auto path) must not raise, and must still refresh
    # both the root and the cascade-reached child's TTL.
    try:
        await parent.asave()
    except PersistentNoScriptError:
        pytest.fail(
            "asave()'s automatic cascade branch did not survive SCRIPT "
            "FLUSH via the shipped run_sha-into-pipeline NOSCRIPT self-heal"
        )

    assert await real_redis_client.ttl(parent.key) > 0
    assert await real_redis_client.ttl(child.key) > 0
