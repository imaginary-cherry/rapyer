import pytest

from rapyer.result import CascadeResult
from tests.integration.foreign_keys.conftest import apply_cascade
from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeAuthor,
    CascadeChainNode,
    CascadeColonPkMember,
    CascadeColonPkOwner,
    CascadeMultiClassDiamondLeaf,
    CascadeMultiClassDiamondMemberA,
    CascadeMultiClassDiamondMemberB,
    CascadeMultiClassDiamondRoot,
    CascadeUnionDepthRoot,
    CascadeUnionDictOwner,
    CascadeUnionListOwner,
    CascadeUnionMemberA,
    CascadeUnionMemberB,
    CascadeUnionOwner,
    CascadeUnionPQOwner,
    CascadeUnionSetOwner,
)

pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")


@pytest.mark.asyncio
async def test_scalar_union_reaches_resolved_member_class(real_redis_client):
    # Arrange
    # The phase tracer: ONE scalar-union FK owner referencing a concrete member.
    # The reached member's class is NOT baked into the edge (the edge carries
    # BOTH CascadeUnionMemberA/B as candidates); it must be resolved server-side
    # from the reached key's {class}:{pk} prefix, membership-checked against the
    # edge's candidates, and re-armed to its OWN resolved class's Meta.ttl --
    # all driven through the PUBLIC aset_ttl(cascade=True) API on real Redis.
    member = await CascadeUnionMemberA(name="reached").asave()
    owner = await CascadeUnionOwner(ref=member.key).asave()
    await real_redis_client.persist(owner.key)
    await real_redis_client.persist(member.key)

    # Act
    result = await owner.aset_ttl(CASCADE_FIXTURE_TTL_SECONDS, cascade=True)

    # Assert
    # A clean union reach: zero danglings, zero class drift, and the reached
    # member re-armed (ttl > 0) to its own class's Meta.ttl. This exercises the
    # D-01 push_child resolution branch, the D-03 mismatched_class counter, the
    # base.py 3-element results[-1] unpack, and the result.py field together,
    # end-to-end through the public API.
    assert result == CascadeResult(
        dangling_children=0, dangling_special=0, mismatched_class=0
    )
    assert await real_redis_client.ttl(member.key) > 0


# --- Task 1: both candidates resolve from the SAME union edge (CMCT-04 adjacency) ---


@pytest.mark.asyncio
async def test_scalar_union_both_members_resolve_and_rearm_from_the_same_edge(
    real_redis_client,
):
    # Arrange
    # ONE union edge (CascadeUnionOwner.ref, candidates == {A, B}) reached by two
    # owners -- one pointing at a member-A key, one at a member-B key. The reached
    # class is NOT baked into the edge; each is resolved server-side from its own
    # {class}:{pk} prefix and EXACT-matched against the shared candidate set. This
    # proves BOTH union members resolve correctly from the same edge, not just the
    # first candidate.
    member_a = await CascadeUnionMemberA(name="a").asave()
    member_b = await CascadeUnionMemberB(name="b").asave()
    owner_a = await CascadeUnionOwner(ref=member_a.key).asave()
    owner_b = await CascadeUnionOwner(ref=member_b.key).asave()
    for key in (owner_a.key, owner_b.key, member_a.key, member_b.key):
        await real_redis_client.persist(key)

    # Act
    result_a = await apply_cascade(real_redis_client, owner_a)
    result_b = await apply_cascade(real_redis_client, owner_b)

    # Assert
    # Member A re-arms from the A-prefix reach; member B re-arms from the B-prefix
    # reach -- exact-prefix membership resolves both candidates, no class drift.
    assert await real_redis_client.ttl(member_a.key) > 0
    assert await real_redis_client.ttl(member_b.key) > 0
    assert result_a[2] == 0
    assert result_b[2] == 0


# --- Task 1: collection-of-union shapes (list / dict) re-arm every referenced member ---


@pytest.mark.asyncio
async def test_list_union_owner_rearms_every_referenced_member_class(real_redis_client):
    # Arrange
    # A list[Reference[A | B]] whose elements MIX both member classes. Every
    # referenced member must resolve from its own key prefix and re-arm to its
    # OWN class's Meta.ttl (CMCT-04/05/07 collection shape).
    member_a = await CascadeUnionMemberA(name="la").asave()
    member_b = await CascadeUnionMemberB(name="lb").asave()
    owner = await CascadeUnionListOwner(refs=[member_a.key, member_b.key]).asave()
    for key in (owner.key, member_a.key, member_b.key):
        await real_redis_client.persist(key)

    # Act
    result = await apply_cascade(real_redis_client, owner)

    # Assert
    for key in (owner.key, member_a.key, member_b.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS
    assert result[2] == 0


@pytest.mark.asyncio
async def test_dict_union_owner_rearms_every_referenced_member_class(real_redis_client):
    # Arrange
    # A dict[str, Reference[A | B]] whose values MIX both member classes.
    member_a = await CascadeUnionMemberA(name="da").asave()
    member_b = await CascadeUnionMemberB(name="db").asave()
    owner = await CascadeUnionDictOwner(
        refs={"x": member_a.key, "y": member_b.key}
    ).asave()
    for key in (owner.key, member_a.key, member_b.key):
        await real_redis_client.persist(key)

    # Act
    result = await apply_cascade(real_redis_client, owner)

    # Assert
    for key in (owner.key, member_a.key, member_b.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS
    assert result[2] == 0


# --- Task 1: SF-held union shapes (RedisSet / RedisPriorityQueue) re-arm both classes ---


@pytest.mark.asyncio
async def test_set_union_owner_rearms_both_member_classes(real_redis_client):
    # Arrange
    # An SF-held RedisSet[Reference[A | B]] holding one member-A key and one
    # member-B key. Both members are reached via the SMEMBERS branch, each
    # resolved from its own prefix and re-armed (CMCT-04/07 SF-set shape).
    member_a = await CascadeUnionMemberA(name="sa").asave()
    member_b = await CascadeUnionMemberB(name="sb").asave()
    owner = await CascadeUnionSetOwner().asave()
    await owner.refs.aadd(member_a.key)
    await owner.refs.aadd(member_b.key)
    for key in (owner.key, member_a.key, member_b.key):
        await real_redis_client.persist(key)

    # Act
    result = await apply_cascade(real_redis_client, owner)

    # Assert
    for key in (owner.key, member_a.key, member_b.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS
    assert result[2] == 0


@pytest.mark.asyncio
async def test_priority_queue_union_owner_rearms_both_member_classes(
    real_redis_client,
):
    # Arrange
    # An SF-held RedisPriorityQueue[Reference[A | B]] holding both member classes.
    # Both are reached via the ZRANGE branch, resolved, and re-armed
    # (CMCT-04/07 SF-priority-queue shape).
    member_a = await CascadeUnionMemberA(name="pa").asave()
    member_b = await CascadeUnionMemberB(name="pb").asave()
    owner = await CascadeUnionPQOwner().asave()
    await owner.queue.apush(member_a.key, priority=1.0)
    await owner.queue.apush(member_b.key, priority=2.0)
    for key in (owner.key, member_a.key, member_b.key):
        await real_redis_client.persist(key)

    # Act
    result = await apply_cascade(real_redis_client, owner)

    # Assert
    for key in (owner.key, member_a.key, member_b.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS
    assert result[2] == 0


# --- Task 1: empty union owners reach no child and never crash (CMCT-07 empty) ---


@pytest.mark.asyncio
async def test_empty_union_owners_reach_no_child_and_do_not_crash(real_redis_client):
    # Arrange
    # Every union FK shape with an EMPTY container: a scalar-less collection, an
    # empty RedisSet, and an empty RedisPriorityQueue. Each must complete the
    # FCALL, re-arm its own root key, reach no child, and never raise.
    list_owner = await CascadeUnionListOwner().asave()
    dict_owner = await CascadeUnionDictOwner().asave()
    set_owner = await CascadeUnionSetOwner().asave()
    pq_owner = await CascadeUnionPQOwner().asave()
    owners = (list_owner, dict_owner, set_owner, pq_owner)
    for owner in owners:
        await real_redis_client.persist(owner.key)

    # Act / Assert (no child reached, root re-armed, zero class drift, no crash)
    for owner in owners:
        result = await apply_cascade(real_redis_client, owner)
        assert await real_redis_client.ttl(owner.key) > 0
        assert result[2] == 0


# --- Task 1: colon-bearing pk resolves via first-colon split (Pitfall 2) ---


@pytest.mark.asyncio
async def test_colon_bearing_pk_member_resolves_via_first_colon_split_and_rearms(
    real_redis_client,
):
    # Arrange
    # A union member whose Key[str] pk itself contains a colon ("tenant:42"), so
    # its full key is "CascadeColonPkMember:tenant:42". Server-side resolution
    # splits on the FIRST colon (string.match '^([^:]+):' mirrors the Python
    # key.setter split(':', maxsplit=1)), so the resolved prefix is the CLASS
    # NAME -- never a pk segment. The member must still be matched as a candidate
    # and re-armed (RESEARCH Pitfall 2).
    member = await CascadeColonPkMember(member_id="tenant:42").asave()
    assert member.key == "CascadeColonPkMember:tenant:42"
    owner = await CascadeColonPkOwner(ref=member.key).asave()
    for key in (owner.key, member.key):
        await real_redis_client.persist(key)

    # Act
    result = await apply_cascade(real_redis_client, owner)

    # Assert
    assert await real_redis_client.ttl(member.key) > 0
    assert result[2] == 0


# --- Task 2: cycle-safe mixed-class diamond over a shared leaf (CMCT-08) ---


@pytest.mark.asyncio
async def test_mixed_class_diamond_shared_leaf_rearmed_via_two_candidate_classes(
    real_redis_client,
):
    # Arrange
    # A single shared leaf FK'd by TWO DIFFERENT candidate classes
    # (CascadeMultiClassDiamondMemberA and ...MemberB). The diamond root's scalar
    # edge is a union over both member classes; whichever candidate it resolves
    # to, the cascade continues on to the SAME shared leaf. Two roots -- one
    # resolving to member-A, one to member-B -- exercise the shared leaf via two
    # DISTINCT candidate-class paths (the CascadeMultiClassDiamondRoot scalar-union
    # fixture only carries one candidate per instance, so the two candidate-class
    # paths are driven by two root instances, mirroring the accepted
    # test_shared_child_via_two_independent_roots pattern). Within each walk the
    # shared leaf is re-armed exactly once at the best budget via the visited
    # best-budget map (the map is unchanged by D-01 -- cycle/diamond dedup is
    # inherited, already proven by test_diamond_shared_child / test_max_budget_wins),
    # and every diamond node is re-armed to its OWN class Meta.ttl with no
    # double-refresh crash.
    leaf = await CascadeMultiClassDiamondLeaf(name="shared").asave()
    member_a = await CascadeMultiClassDiamondMemberA(leaf=leaf.key).asave()
    member_b = await CascadeMultiClassDiamondMemberB(leaf=leaf.key).asave()
    root_a = await CascadeMultiClassDiamondRoot(member=member_a.key).asave()
    root_b = await CascadeMultiClassDiamondRoot(member=member_b.key).asave()
    for key in (root_a.key, root_b.key, member_a.key, member_b.key, leaf.key):
        await real_redis_client.persist(key)

    # Act / Assert -- candidate-class path A: root -> member A -> shared leaf.
    result_a = await apply_cascade(real_redis_client, root_a)
    for key in (root_a.key, member_a.key, leaf.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS
    assert result_a[2] == 0

    # Re-arm the leaf's dangling state, then candidate-class path B:
    # root -> member B -> the SAME shared leaf. The leaf re-arms via either
    # candidate-class path, never a collision or double-refresh error.
    await real_redis_client.persist(leaf.key)
    result_b = await apply_cascade(real_redis_client, root_b)
    for key in (root_b.key, member_b.key, leaf.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS
    assert result_b[2] == 0


# --- Task 2: per-subtree depth budget truncates THROUGH a resolved-class edge ---


@pytest.mark.asyncio
async def test_depth_budget_truncates_through_a_resolved_class_union_edge(
    real_redis_client,
):
    # Arrange
    # A 3-node blanket-decrementing CascadeChainNode chain (c1 -> c2 -> c3),
    # entered THROUGH CascadeUnionDepthRoot's union edge (candidates:
    # CascadeChainNode | CascadeUnionMemberB) capped at depth=1. entry resolves
    # c1's class from its "CascadeChainNode:" prefix among the edge's candidates
    # and carries the reset depth=1 budget into c1's subtree:
    #   c1 at budget 1  -> re-armed
    #   c2 at budget 0  -> re-armed (the one in-budget blanket hop)
    #   c3 at budget -1 -> truncated, NOT re-armed
    # The budget argument and the visited best-budget map pass through push_child
    # UNCHANGED (D-01 resolves only the CHILD's class), so the budget arithmetic is
    # inherited from the single-target path already proven by
    # test_cascade_depth_and_gate.py::test_independent_sibling_depth_budgets. This
    # test adds the DIRECT multi-class leg so CMCT-08's depth-budget clause is
    # traceable, not merely indirect.
    c3 = await CascadeChainNode(name="c3").asave()
    c2 = await CascadeChainNode(name="c2", next=c3.key).asave()
    c1 = await CascadeChainNode(name="c1", next=c2.key).asave()
    root = await CascadeUnionDepthRoot(entry=c1.key).asave()
    all_keys = (root.key, c1.key, c2.key, c3.key)
    for key in all_keys:
        await real_redis_client.persist(key)

    # Act
    await apply_cascade(real_redis_client, root)

    # Assert
    refreshed = {key for key in all_keys if await real_redis_client.ttl(key) > 0}
    assert refreshed == {root.key, c1.key, c2.key}
    assert await real_redis_client.ttl(c3.key) in (-1, -2)


# --- Task 2: dead-end contracts -- counted non-candidate vs uncounted corrupt ---


@pytest.mark.asyncio
async def test_non_candidate_reach_is_skipped_and_tallied_as_class_drift(
    real_redis_client,
):
    # Arrange
    # A union owner's ref points at a saved CascadeAuthor key. CascadeAuthor is a
    # registered, plan-present model but is NOT among CascadeUnionOwner.ref's
    # candidates ({CascadeUnionMemberA, CascadeUnionMemberB}). The reach resolves
    # to a valid-but-non-candidate class: it MUST be skipped (no TTL applied) AND
    # tallied in the FCALL's third return element (mismatched_class), giving
    # operators a class-drift signal (D-03, CMCT-10).
    #
    # The tally is asserted at REACH time (at-least-once, NOT deduped via the
    # visited map): per the LOCKED D-03 choice, the requirement is observability
    # of drift, not exact-once accounting -- a non-candidate reached via two paths
    # may count more than once, and that is acceptable.
    author = await CascadeAuthor(name="drift").asave()
    owner = await CascadeUnionOwner(ref=author.key).asave()
    for key in (owner.key, author.key):
        await real_redis_client.persist(key)

    # Act
    result = await apply_cascade(real_redis_client, owner)

    # Assert
    # No misapplied TTL on the non-candidate key ...
    assert await real_redis_client.ttl(author.key) in (-1, -2)
    # ... and the drift is observed (mismatched_class incremented).
    assert result[2] == 1
    # The root itself still re-arms -- the non-candidate reach is a safe dead-end,
    # never an aborted FCALL (T-02-07 mitigation).
    assert await real_redis_client.ttl(owner.key) > 0


@pytest.mark.asyncio
async def test_corrupt_no_colon_reach_is_a_silent_uncounted_dead_end(
    real_redis_client,
):
    # Arrange
    # A union owner's ref holds a corrupt, colon-less value. string.match on the
    # first-colon pattern yields nil, so the reach is the EXISTING silent dead-end
    # (skip, no crash) and is NOT tallied as class drift -- only a parsed-but-non-
    # candidate PREFIX is counted (D-03, CMCT-10). This distinguishes a corrupt
    # reach (uncounted) from a class-drift reach (counted, previous test).
    owner = await CascadeUnionOwner(ref="corrupt-no-colon-value").asave()
    await real_redis_client.persist(owner.key)

    # Act
    result = await apply_cascade(real_redis_client, owner)

    # Assert
    # No class-drift tally for a corrupt (colon-less) reach ...
    assert result[2] == 0
    # ... and the FCALL completes, re-arming the root (safe dead-end, T-02-07).
    assert await real_redis_client.ttl(owner.key) > 0
