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
    member = await CascadeUnionMemberA(name="reached").asave()
    owner = await CascadeUnionOwner(ref=member.key).asave()
    await real_redis_client.persist(owner.key)
    await real_redis_client.persist(member.key)

    # Act
    result = await owner.aset_ttl(CASCADE_FIXTURE_TTL_SECONDS, cascade=True)

    # Assert
    assert result == CascadeResult(
        dangling_children=0, dangling_special=0, mismatched_class=0
    )
    assert await real_redis_client.ttl(member.key) > 0


# --- Both candidates resolve from the same union edge ---


@pytest.mark.asyncio
async def test_scalar_union_both_members_resolve_and_rearm_from_the_same_edge(
    real_redis_client,
):
    # Arrange
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
    assert await real_redis_client.ttl(member_a.key) > 0
    assert await real_redis_client.ttl(member_b.key) > 0
    assert result_a[2] == 0
    assert result_b[2] == 0


# --- Collection-of-union shapes (list / dict) ---


@pytest.mark.asyncio
async def test_list_union_owner_rearms_every_referenced_member_class(real_redis_client):
    # Arrange
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


# --- SF-held union shapes (RedisSet / RedisPriorityQueue) ---


@pytest.mark.asyncio
async def test_set_union_owner_rearms_both_member_classes(real_redis_client):
    # Arrange
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


# --- Empty union owners reach no child and never crash ---


@pytest.mark.asyncio
async def test_empty_union_owners_reach_no_child_and_do_not_crash(real_redis_client):
    # Arrange
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


# --- Colon-bearing pk resolves via the first-colon split ---


@pytest.mark.asyncio
async def test_colon_bearing_pk_member_resolves_via_first_colon_split_and_rearms(
    real_redis_client,
):
    # Arrange
    member = await CascadeColonPkMember(member_id="tenant:42").asave()
    assert member.key == "CascadeColonPkMember:tenant:42"
    owner = await CascadeColonPkOwner(ref=member.key).asave()
    for key in (owner.key, member.key):
        await real_redis_client.persist(key)

    # Act
    result = await apply_cascade(real_redis_client, owner)

    # Assert -- the first-colon split yields the class, not a pk segment.
    assert await real_redis_client.ttl(member.key) > 0
    assert result[2] == 0


# --- Cycle-safe mixed-class diamond over a shared leaf ---


@pytest.mark.asyncio
async def test_mixed_class_diamond_shared_leaf_rearmed_via_two_candidate_classes(
    real_redis_client,
):
    # Arrange
    leaf = await CascadeMultiClassDiamondLeaf(name="shared").asave()
    member_a = await CascadeMultiClassDiamondMemberA(leaf=leaf.key).asave()
    member_b = await CascadeMultiClassDiamondMemberB(leaf=leaf.key).asave()
    # One root instance resolves to one candidate, so two roots drive the two class paths.
    root_a = await CascadeMultiClassDiamondRoot(member=member_a.key).asave()
    root_b = await CascadeMultiClassDiamondRoot(member=member_b.key).asave()
    for key in (root_a.key, root_b.key, member_a.key, member_b.key, leaf.key):
        await real_redis_client.persist(key)

    # Act / Assert -- candidate-class path A: root -> member A -> shared leaf.
    result_a = await apply_cascade(real_redis_client, root_a)
    for key in (root_a.key, member_a.key, leaf.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS
    assert result_a[2] == 0

    # Act / Assert -- path B reaches the same leaf, with no collision on re-arm.
    await real_redis_client.persist(leaf.key)
    result_b = await apply_cascade(real_redis_client, root_b)
    for key in (root_b.key, member_b.key, leaf.key):
        assert 0 < await real_redis_client.ttl(key) <= CASCADE_FIXTURE_TTL_SECONDS
    assert result_b[2] == 0


# --- Per-subtree depth budget truncates through a resolved-class edge ---


@pytest.mark.asyncio
async def test_depth_budget_truncates_through_a_resolved_class_union_edge(
    real_redis_client,
):
    # Arrange
    c3 = await CascadeChainNode(name="c3").asave()
    c2 = await CascadeChainNode(name="c2", next=c3.key).asave()
    c1 = await CascadeChainNode(name="c1", next=c2.key).asave()
    # The union edge's depth=1 budget is carried into the resolved chain: c3 falls out of budget.
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


# --- Dead-end contracts: counted non-candidate vs uncounted corrupt ---


@pytest.mark.asyncio
async def test_non_candidate_reach_is_skipped_and_tallied_as_class_drift(
    real_redis_client,
):
    # Arrange
    author = await CascadeAuthor(name="drift").asave()
    # CascadeAuthor is registered and in the plan, but is not a candidate of this edge.
    owner = await CascadeUnionOwner(ref=author.key).asave()
    for key in (owner.key, author.key):
        await real_redis_client.persist(key)

    # Act
    result = await apply_cascade(real_redis_client, owner)

    # Assert -- no TTL on the non-candidate key, but the drift is tallied.
    assert await real_redis_client.ttl(author.key) in (-1, -2)
    assert result[2] == 1
    # The reach is a safe dead-end, never an aborted FCALL: the root still re-arms.
    assert await real_redis_client.ttl(owner.key) > 0


@pytest.mark.asyncio
async def test_corrupt_no_colon_reach_is_a_silent_uncounted_dead_end(
    real_redis_client,
):
    # Arrange
    owner = await CascadeUnionOwner(ref="corrupt-no-colon-value").asave()
    await real_redis_client.persist(owner.key)

    # Act
    result = await apply_cascade(real_redis_client, owner)

    # Assert -- only a parsed-but-non-candidate prefix counts, so a corrupt reach does not.
    assert result[2] == 0
    assert await real_redis_client.ttl(owner.key) > 0
