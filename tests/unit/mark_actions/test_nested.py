from unittest.mock import ANY

import pytest

from rapyer.actions import ActionGroup, mark_actions
from tests.models.simple_types import TTLRefreshTestModel
from tests.unit.mark_actions.conftest import assert_action, maybe_install_v2


@pytest.mark.asyncio
async def test_nested_decorated_calls_flush_only_once(flush_mock, mark_version):
    # Arrange
    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def inner(m):
        return None

    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def outer(m):
        await inner(m)

    inner, outer = maybe_install_v2(mark_version, inner, outer)

    model = TTLRefreshTestModel(name="single-flush")

    # Act
    await outer(model)

    # Assert - outer and inner registered the same instance, so two entries (dedup is later).
    flush_mock.assert_awaited_once_with(
        [
            (model, ActionGroup.UPDATE),
            (model, ActionGroup.UPDATE),
        ],
        ANY,
    )


@pytest.mark.asyncio
async def test_nested_decorated_calls_with_different_models_collect_all_targets(
    flush_mock, mark_version
):
    # Arrange
    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def inner(m):
        return None

    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def outer(m, other):
        await inner(other)

    inner, outer = maybe_install_v2(mark_version, inner, outer)

    a = TTLRefreshTestModel(name="outer-a")
    b = TTLRefreshTestModel(name="inner-b")

    # Act
    await outer(a, b)

    # Assert: outer registers `a` first (target=SELF), then inner registers `b`.
    flush_mock.assert_awaited_once_with(
        [
            (a, ActionGroup.UPDATE),
            (b, ActionGroup.UPDATE),
        ],
        ANY,
    )


@pytest.mark.asyncio
async def test_nested_same_model_dedups_with_merged_action_groups(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    @mark_actions(ActionGroup.READ, version=mark_version)
    async def inner(m):
        return None

    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def outer(m):
        await inner(m)

    inner, outer = maybe_install_v2(mark_version, inner, outer)

    model = TTLRefreshTestModel(name="merge-actions")

    # Act
    await outer(model)

    # Assert
    assert len(refresh_calls) == 1
    assert refresh_calls[0].model is model
    assert_action(refresh_calls[0], ActionGroup.UPDATE | ActionGroup.READ, mark_version)


@pytest.mark.asyncio
async def test_dedup_by_key_with_different_instance_data(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    @mark_actions(ActionGroup.READ, version=mark_version)
    async def inner(m):
        return None

    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def outer(m, other):
        await inner(other)

    inner, outer = maybe_install_v2(mark_version, inner, outer)

    m1 = TTLRefreshTestModel(name="first-data", age=10)
    m2 = TTLRefreshTestModel(name="second-data", age=99)
    # Force m2 to share m1's key while keeping a different instance + data.
    m2.pk = m1.pk
    assert m1.key == m2.key
    assert m1 is not m2
    assert m1.name != m2.name

    # Act: outer registers m1 via target=SELF; inner registers m2 via target=SELF.
    await outer(m1, m2)

    # Assert - one refresh (deduped by key), groups OR-merged, first registered instance kept.
    assert len(refresh_calls) == 1
    assert refresh_calls[0].model is m1
    assert_action(refresh_calls[0], ActionGroup.UPDATE | ActionGroup.READ, mark_version)


@pytest.mark.asyncio
async def test_nested_different_models_refreshed_separately(
    setup_fake_redis, refresh_calls, mark_version
):
    # Arrange
    @mark_actions(ActionGroup.READ, version=mark_version)
    async def inner(m):
        return None

    @mark_actions(ActionGroup.UPDATE, version=mark_version)
    async def outer(m, other):
        await inner(other)

    inner, outer = maybe_install_v2(mark_version, inner, outer)

    a = TTLRefreshTestModel(name="dist-a")
    b = TTLRefreshTestModel(name="dist-b")

    # Act
    await outer(a, b)

    # Assert: each model gets its own refresh, with its own action group.
    by_key = {c.model.key: c for c in refresh_calls}
    assert set(by_key) == {a.key, b.key}
    assert_action(by_key[a.key], ActionGroup.UPDATE, mark_version)
    assert_action(by_key[b.key], ActionGroup.READ, mark_version)
