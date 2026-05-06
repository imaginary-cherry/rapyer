from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock

import pytest

import rapyer.actions
from rapyer.actions import ActionGroup, install_action_for_meta
from tests.models.simple_types import TTLRefreshTestModel


@pytest.fixture(params=["v1", "v2"])
def mark_version(request):
    """Run each test against both ``mark_actions`` versions.

    For v2 the wrap is decided at install time, not decoration time, so tests
    that exercise wrapper behavior must route the decorated function through
    ``maybe_install_v2`` after decorating.
    """
    return request.param


class RefreshAllMeta:
    """Meta stub that opts into refresh for every action group — used by tests
    that just want the v2 wrap to fire so the v1 and v2 codepaths converge."""

    ttl = 60
    refresh_ttl = ActionGroup.all(for_ttl=True)


def maybe_install_v2(mark_version, *funcs):
    """No-op for v1; for v2, install each func against a refresh-all Meta.

    Returns a single func or a tuple matching the input arity.
    """
    if mark_version == "v1":
        result = funcs
    else:
        result = tuple(install_action_for_meta(f, RefreshAllMeta) for f in funcs)
    return result[0] if len(result) == 1 else result


@dataclass
class RefreshCall:
    model: TTLRefreshTestModel
    action: Optional[ActionGroup]
    can_use_pipeline: bool


@pytest.fixture
def setup_fake_redis(fake_redis_client):
    """Swap TTLRefreshTestModel.Meta.redis to a fakeredis client for the test."""
    original_redis = TTLRefreshTestModel.Meta.redis
    original_is_fake = TTLRefreshTestModel.Meta.is_fake_redis
    TTLRefreshTestModel.Meta.redis = fake_redis_client
    TTLRefreshTestModel.Meta.is_fake_redis = True
    yield fake_redis_client
    TTLRefreshTestModel.Meta.redis = original_redis
    TTLRefreshTestModel.Meta.is_fake_redis = original_is_fake


@pytest.fixture
def refresh_calls(monkeypatch):
    """Replace TTLRefreshTestModel.refresh_ttl_if_needed with a recorder."""
    calls: list[RefreshCall] = []

    async def capture(self, can_use_pipeline: bool = False, action=None):
        calls.append(
            RefreshCall(
                model=self,
                action=action,
                can_use_pipeline=can_use_pipeline,
            )
        )

    monkeypatch.setattr(TTLRefreshTestModel, "refresh_ttl_if_needed", capture)
    monkeypatch.setattr(TTLRefreshTestModel, "refresh_ttl", capture)
    return calls


@pytest.fixture
def flush_mock(monkeypatch):
    """Replace rapyer.actions.flush_action_targets with an AsyncMock."""
    mock = AsyncMock()
    monkeypatch.setattr(rapyer.actions, "flush_action_targets", mock)
    return mock
