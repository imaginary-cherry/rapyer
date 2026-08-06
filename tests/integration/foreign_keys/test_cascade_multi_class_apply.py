import pytest

from rapyer.result import CascadeResult
from tests.integration.foreign_keys.conftest import apply_cascade
from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeColonPkMember,
    CascadeColonPkOwner,
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
