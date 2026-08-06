"""fakeredis no-op divergence proof for a UNION-FK owner (CMCT-11 fallback leg).

The cascade Redis Function NEVER runs on fakeredis (no Redis Functions there);
``aset_ttl(cascade=True)`` takes the native-EXPIRE fast path over the ROOT's own
keys only -- no traversal. These tests pin exactly that documented divergence for
a multi-class (union) FK owner: the root's own keys (its main document key and/or
its own SF-container key) are re-armed, but a REACHED union member is NOT (the
Function that would resolve its {class}:{pk} prefix and re-arm it never executes
here). The returned ``CascadeResult`` is the zero-drift fast-path value
``mismatched_class=0`` with zero danglings -- the native fast path produces no
counters at all, including zero class drift.

This is the fallback leg ONLY. It deliberately asserts NO traversal: the real
multi-class reach proof lives in the real-Redis integration suite
(``tests/integration/foreign_keys/test_cascade_multi_class_apply.py``), gated by
``requires_redis_functions``. Mirrors
``test_cascade_sf_held_ref_fakeredis_fallback.py`` exactly, for a union target.
"""

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

# The multi-candidate union fixtures are deliberately NOT part of the shared
# CASCADE_PLANNER_MODELS list in conftest.py -- that list is the pre-phase
# single-target set guarded byte-identical by test_no_preexisting_single_target
# _model_is_silently_expanded. Wire the union models onto the SAME fakeredis
# client the conftest fixture set up, restoring them afterwards so no global
# registry state leaks into other tests.
_UNION_MODELS = [
    CascadeUnionMemberA,
    CascadeUnionMemberB,
    CascadeUnionOwner,
    CascadeUnionSetOwner,
]
_DECLARED_UNION_CASCADE_TTL = {
    model: model.Meta.cascade_ttl for model in _UNION_MODELS
}


@pytest_asyncio.fixture
async def setup_fake_redis_for_union_cascade_apply(
    setup_fake_redis_for_cascade_apply,
    fake_redis_client,
):
    """Extend the cascade-apply fakeredis wiring to the union fixtures used here,
    onto the same fake client (scripts already registered by the base fixture)."""
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
    # Arrange: a scalar union owner (inline Reference[A | B]) referencing a
    # concrete member. The inline FK lives in the owner's OWN JSON document, so
    # the owner has a main document key. On fakeredis the member is never reached
    # (the Function never traverses), proving the documented no-op divergence:
    # the root's OWN main key re-arms, the reached member does NOT.
    member = await CascadeUnionMemberA(name="reached").asave()
    owner = await CascadeUnionOwner(ref=member.key).asave()

    await fake_redis_client.persist(owner.key)
    await fake_redis_client.persist(member.key)

    # Act
    result = await owner.aset_ttl(TTL_SECONDS, cascade=True)

    # Assert
    # Zero-drift fast-path result: the native EXPIRE loop tallies nothing,
    # including zero class drift (mismatched_class=0).
    assert result == CascadeResult(
        dangling_children=0, dangling_special=0, mismatched_class=0
    )
    # Root's OWN main key refreshed ...
    assert await fake_redis_client.ttl(owner.key) > 0
    # ... reached union member NOT re-armed (no traversal on fakeredis).
    assert await fake_redis_client.ttl(member.key) in (-1, -2)


@pytest.mark.asyncio
async def test_union_set_owner_cascade_on_fakeredis_refreshes_own_container_not_member(
    setup_fake_redis_for_union_cascade_apply,
    fake_redis_client,
):
    # Arrange: an SF-held union owner (RedisSet[Reference[A | B]]) holding one
    # concrete union member. This exercises the OWN-CONTAINER leg of the fast
    # path: on fakeredis the owner's own SET container key is re-armed via a plain
    # EXPIRE, but the edge to the member is NEVER followed -- the Function that
    # would resolve the member's {class}:{pk} prefix does not run here.
    #
    # NOTE: CascadeUnionSetOwner declares only the RedisSet special field (no
    # scalar field), so its main JSON document is empty and no main document key
    # is persisted on asave() -- the own-key refresh in the SF case is therefore
    # proven on the CONTAINER key. The scalar-owner test above covers the own
    # MAIN-key refresh leg.
    member = await CascadeUnionMemberA(name="reached").asave()
    owner = await CascadeUnionSetOwner().asave()
    await owner.refs.aadd(ForeignKey(member.key))

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
