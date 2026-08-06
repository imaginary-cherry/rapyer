import pytest

from rapyer.result import CascadeResult
from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeUnionMemberA,
    CascadeUnionOwner,
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
