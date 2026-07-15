import asyncio

import pytest

from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")

ROOT_TTL_SECONDS = 120


@pytest.mark.asyncio
async def test_cascade_races_concurrent_fk_reassignment_reflects_one_consistent_snapshot_sanity(
    real_redis_client,
):
    """
    Races (1) parent.aset_ttl(ttl, cascade=True) against (2) a concurrent
    write that reassigns parent.child to a different saved child and re-saves
    it. This proves that Redis's single-threaded EVALSHA execution guarantees
    the cascade script observes exactly ONE consistent snapshot of parent's
    child field -- i.e. that no client-side TOCTOU gap was introduced by the
    ensure_pipeline action-boundary wiring. It does NOT prove Redis itself
    needed proving; Redis's own atomicity is a given.
    """
    # Arrange
    child_a = await CascadeSpecialChild().asave()
    await child_a.tags.aadd("x")
    await child_a.scores.apush(1.0, priority=1.0)
    child_b = await CascadeSpecialChild().asave()
    await child_b.tags.aadd("y")
    await child_b.scores.apush(2.0, priority=2.0)
    parent = await CascadeSpecialParent(child=child_a.key).asave()
    for key in (child_a.key, child_b.key, parent.key):
        await real_redis_client.persist(key)

    # Act
    async def _reassign_child_and_save():
        parent.child = child_b.key
        await parent.asave()

    cascade_result, _ = await asyncio.gather(
        parent.aset_ttl(ROOT_TTL_SECONDS, cascade=True),
        _reassign_child_and_save(),
    )

    # Assert
    # The explicit cascade never resolved to a dangling/garbage
    # reference -- whichever consistent snapshot of parent.child it observed
    # (the old graph, child_a, or the already-reassigned new graph, child_b),
    # that child genuinely existed. A torn/mixed read spanning both graphs
    # could only manifest here as a bogus dangling count.
    assert cascade_result.dangling_children == 0
    assert cascade_result.dangling_special == 0

    child_a_ttl = await real_redis_client.ttl(child_a.key)
    child_b_ttl = await real_redis_client.ttl(child_b.key)

    # child_b is unconditionally reached: the concurrent write's own asave()
    # call auto-cascades inside the SAME atomic transaction as its
    # JSON.SET of the reassigned `child` field, so once that transaction
    # commits, child_b has already been refreshed by its own cascade --
    # independent of how the explicit aset_ttl(cascade=True) call's EVALSHA
    # interleaves with it.
    assert 0 < child_b_ttl <= CASCADE_FIXTURE_TTL_SECONDS

    # child_a is reached if and only if the explicit aset_ttl(cascade=True)
    # call's EVALSHA executed against the pre-mutation snapshot
    # (parent.child == child_a, read server-side via a single atomic
    # JSON.GET) BEFORE the concurrent transaction reassigned it -- a fully
    # valid "old graph" read. If the concurrent transaction committed first
    # instead, aset_ttl's EVALSHA observes the already-reassigned child_b (a
    # fully valid "new graph" read) and child_a is never touched. Either
    # state is legitimate; a mixed/torn read is not -- ruled out above by
    # dangling_children == 0 and dangling_special == 0.
    assert child_a_ttl in (-1, -2) or 0 < child_a_ttl <= CASCADE_FIXTURE_TTL_SECONDS
