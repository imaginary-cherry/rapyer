"""fakeredis has no Redis Functions, so a union-FK owner re-arms its own keys and never traverses."""

import pytest
import pytest_asyncio

from rapyer.result import CascadeResult
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.redis_set import RedisSet
from rapyer.types.relational import resolve_relational_targets
from tests.models.cascade_types import (
    CascadeUnionMemberA,
    CascadeUnionMemberB,
    CascadeUnionOwner,
    CascadeUnionSetOwner,
)

TTL_SECONDS = 120

# Kept out of conftest's CASCADE_PLANNER_MODELS, which is guarded byte-identical.
_UNION_MODELS = [
    CascadeUnionMemberA,
    CascadeUnionMemberB,
    CascadeUnionOwner,
    CascadeUnionSetOwner,
]
_DECLARED_UNION_CASCADE_TTL = {model: model.Meta.cascade_ttl for model in _UNION_MODELS}


@pytest_asyncio.fixture
async def setup_fake_redis_for_union_cascade_apply(
    setup_fake_redis_for_cascade_apply,
    fake_redis_client,
):
    """Extend the cascade-apply fakeredis wiring to the union fixtures used here."""
    originals = {}
    for model in _UNION_MODELS:
        originals[model] = (
            model.Meta.redis,
            model.Meta.is_fake_redis,
            model.Meta.cascade_ttl,
        )
        model.Meta.redis = fake_redis_client
        model.Meta.is_fake_redis = True
        model.Meta.cascade_ttl = _DECLARED_UNION_CASCADE_TTL[model]
    resolve_relational_targets(_UNION_MODELS)
    yield
    for model, (redis, is_fake, cascade_ttl) in originals.items():
        model.Meta.redis = redis
        model.Meta.is_fake_redis = is_fake
        model.Meta.cascade_ttl = cascade_ttl


@pytest.mark.asyncio
async def test_scalar_union_owner_cascade_on_fakeredis_refreshes_own_main_key_not_member(
    setup_fake_redis_for_union_cascade_apply,
    fake_redis_client,
):
    # Arrange
    member = await CascadeUnionMemberA(name="reached").asave()
    owner = await CascadeUnionOwner(ref=member.key).asave()

    await fake_redis_client.persist(owner.key)
    await fake_redis_client.persist(member.key)

    # Act
    result = await owner.aset_ttl(TTL_SECONDS, cascade=True)

    # Assert -- the native EXPIRE loop tallies nothing, class drift included.
    assert result == CascadeResult(
        dangling_children=0, dangling_special=0, mismatched_class=0
    )
    assert await fake_redis_client.ttl(owner.key) > 0
    # The reached member is not re-armed: nothing traverses on fakeredis.
    assert await fake_redis_client.ttl(member.key) in (-1, -2)


@pytest.mark.asyncio
async def test_union_set_owner_cascade_on_fakeredis_refreshes_own_container_not_member(
    setup_fake_redis_for_union_cascade_apply,
    fake_redis_client,
):
    # Arrange
    member = await CascadeUnionMemberA(name="reached").asave()
    owner = await CascadeUnionSetOwner().asave()
    await owner.refs.aadd(ForeignKey(member.key))

    # This owner declares no scalar field, so its own-key refresh shows on the container.
    refs_key = RedisSet.special_field_key(owner.key, "refs")
    await fake_redis_client.persist(refs_key)
    await fake_redis_client.persist(member.key)

    # Act
    result = await owner.aset_ttl(TTL_SECONDS, cascade=True)

    # Assert
    assert result == CascadeResult(
        dangling_children=0, dangling_special=0, mismatched_class=0
    )
    # Root's OWN container key refreshed ...
    assert await fake_redis_client.ttl(refs_key) > 0
    # ... reached union member NOT re-armed (documented no-op divergence).
    assert await fake_redis_client.ttl(member.key) in (-1, -2)
