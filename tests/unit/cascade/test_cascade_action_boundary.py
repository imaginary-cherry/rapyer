from unittest.mock import patch

import pytest

from rapyer.result import CascadeResult
from tests.models.cascade_types import (
    CascadeBookPlain,
    CascadeSpecialChild,
    CascadeSpecialParent,
)

ROOT_TTL_SECONDS = 120


pytestmark = pytest.mark.usefixtures("setup_fake_redis_for_cascade_apply")


@pytest.mark.asyncio
async def test_aset_ttl_without_cascade_flag_only_refreshes_parent_own_keys(
    fake_redis_client,
):
    # Arrange
    child = await CascadeSpecialChild().asave()
    parent = await CascadeSpecialParent(child=child.key).asave()
    await fake_redis_client.persist(child.key)

    # Act
    result = await parent.aset_ttl(ROOT_TTL_SECONDS)

    # Assert
    # Only the parent's own key changes; the child is never touched.
    assert result is None
    assert await fake_redis_client.ttl(parent.key) > 0
    assert await fake_redis_client.ttl(child.key) == -1


@pytest.mark.asyncio
async def test_aset_ttl_cascade_true_on_fakeredis_refreshes_only_root_no_traversal(
    fake_redis_client,
):
    # Arrange
    # Cascade edge-following is real-Redis-only; on fakeredis aset_ttl(cascade=True)
    # refreshes only the root's own keys and reports zero danglings.
    child = await CascadeSpecialChild().asave()
    parent = await CascadeSpecialParent(child=child.key).asave()
    await fake_redis_client.persist(child.key)

    # Act
    result = await parent.aset_ttl(ROOT_TTL_SECONDS, cascade=True)

    # Assert
    assert result == CascadeResult(dangling_children=0, dangling_special=0)
    assert await fake_redis_client.ttl(parent.key) > 0
    assert await fake_redis_client.ttl(child.key) == -1


@pytest.mark.asyncio
async def test_asave_on_fakeredis_refreshes_own_key_via_expire_not_fcall(
    fake_redis_client,
):
    # Act
    # refresh_ttl on fakeredis re-arms the root's own keys via EXPIRE, never FCALL.
    with patch("rapyer.base.scripts_registry.run_fcall") as mock_run_fcall:
        model = await CascadeBookPlain(author="CascadeAuthor:fake").asave()

    # Assert
    mock_run_fcall.assert_not_called()
    assert await fake_redis_client.ttl(model.key) > 0
