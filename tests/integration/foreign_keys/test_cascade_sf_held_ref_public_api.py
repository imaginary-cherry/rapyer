import pytest

from tests.models.cascade_types import (
    CascadeAuthor,
    CascadePQRefParent,
    CascadeSetRefParent,
)

pytestmark = pytest.mark.usefixtures("setup_real_redis_for_cascade_apply")


# --- Test A (CASF-04/05): asave() fires the cascade Function for an SF-only parent ---


@pytest.mark.asyncio
async def test_asave_refreshes_set_held_ref_child_ttl(real_redis_client):
    # Arrange
    parent = await CascadeSetRefParent().asave()
    author = await CascadeAuthor(name="a").asave()
    await parent.refs.aadd(author.key)
    for key in (parent.key, author.key):
        await real_redis_client.persist(key)

    # Act (public API only, no internal cascade-invocation helper)
    await parent.asave()

    # Assert
    assert await real_redis_client.ttl(author.key) > 0


# --- Test B (CASF-04/05): aset_ttl(cascade=True) fires the cascade Function ---


@pytest.mark.asyncio
async def test_aset_ttl_cascade_refreshes_set_held_ref_child_ttl(real_redis_client):
    # Arrange
    parent = await CascadeSetRefParent().asave()
    author = await CascadeAuthor(name="a").asave()
    await parent.refs.aadd(author.key)
    for key in (parent.key, author.key):
        await real_redis_client.persist(key)

    # Act
    result = await parent.aset_ttl(parent.Meta.ttl, cascade=True)

    # Assert
    assert await real_redis_client.ttl(author.key) > 0
    assert result.dangling_children == 0


# --- Test C (CASF-04/05/06): PQ-held ref shape, via asave() ---


@pytest.mark.asyncio
async def test_asave_refreshes_pq_held_ref_child_ttl(real_redis_client):
    # Arrange
    parent = await CascadePQRefParent().asave()
    author = await CascadeAuthor(name="a").asave()
    await parent.queue.apush(author.key, priority=1.0)
    for key in (parent.key, author.key):
        await real_redis_client.persist(key)

    # Act (public API only, no internal cascade-invocation helper)
    await parent.asave()

    # Assert
    assert await real_redis_client.ttl(author.key) > 0
