from dataclasses import dataclass
from typing import Optional

import pytest

from rapyer.actions import ActionGroup
from tests.models.simple_types import TTLRefreshTestModel


@dataclass
class RefreshCall:
    model: TTLRefreshTestModel
    action: Optional[ActionGroup]
    initial: bool
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

    async def capture(
        self, can_use_pipeline: bool = False, action=None, initial: bool = False
    ):
        calls.append(
            RefreshCall(
                model=self,
                action=action,
                initial=initial,
                can_use_pipeline=can_use_pipeline,
            )
        )

    monkeypatch.setattr(TTLRefreshTestModel, "refresh_ttl_if_needed", capture)
    return calls
