import asyncio
import inspect
from abc import ABC
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio.client import Pipeline, Redis

import rapyer.actions as actions_module
from rapyer import AtomicRedisModel
from rapyer.actions import ActionGroup
from tests.coverage_helpers import (
    COVER_TTL_NO_REFRESH,
    COVER_TTL_REFRESH,
    COVER_TTL_UPDATE_ONCE,
    SPECIAL_FIELD_TTL_REFRESH,
    is_action_for_refresh_sf,
    special_field_cover_marker,
)
from tests.integration.actions.base import ActionTestBase
from tests.integration.conftest import REDUCED_TTL_SECONDS
from tests.integration.special_types.adapters import (
    SPECIAL_FIELD_ADAPTERS,
    SpecialFieldAdapter,
)


class TTLActionTestBase(ActionTestBase, ABC):
    """
    Extension of :class:`ActionTestBase` that also exercises TTL refresh
    behavior for async actions decorated with ``@mark_actions``.
    """

    model_exists_before_action: bool = True

    skip_ttl_refresh: ClassVar[str | None] = None
    """If set to a reason string, :meth:`test_ttl_refresh_on_action` is skipped
    with that reason."""

    skip_ttl_no_refresh: ClassVar[str | None] = None
    """If set to a reason string, :meth:`test_ttl_no_refresh_on_action` is
    skipped with that reason."""

    def models_to_check_ttl(self):
        return self.created_models

    def all_keys_to_check(self):
        keys = []
        for model in self.models_to_check_ttl():
            keys.extend(self.ttl_keys(model))
        return keys

    def ttl_keys(self, model: AtomicRedisModel) -> list[str]:
        """Redis keys whose TTL should be asserted. Default: ``[model.key]``.

        Override for actions on special fields to include extra keys such
        as ``model.<field>.special_key``.
        """
        return [model.key]

    async def _setup_ttl_data(self) -> list[AtomicRedisModel]:
        models = await self.setup_data()
        await self.set_ttl(models)
        return models

    async def set_ttl(self, models: list[AtomicRedisModel]):
        for inst in models:
            for key in self.ttl_keys(inst):
                await self.real_redis_client.expire(key, REDUCED_TTL_SECONDS)

    @pytest.mark.asyncio
    async def _setup_test_special_field_ttl_refresh(self, adapter: SpecialFieldAdapter):
        # Arrange
        wrapped = await self.create_sp_models(adapter)

        await self.set_ttl(wrapped)
        await adapter.set_ttl(wrapped[0], REDUCED_TTL_SECONDS)

        ttls_before = None
        if self.model_exists_before_action:
            ttls_before: list[int] = await adapter.get_additional_ttl(wrapped[0])

        # Act
        with patch.object(
            type(wrapped[0]).Meta, "refresh_ttl", ActionGroup.all(for_ttl=True)
        ):
            await self.perform_action(wrapped[0])

        # Assert
        ttl_configured = type(wrapped[0]).Meta.ttl
        afters = await adapter.get_additional_ttl(wrapped[0])
        keys = adapter.additional_ttl_keys(wrapped[0])
        if self.model_exists_before_action and ttls_before is not None:
            for key, after, before in zip(keys, afters, ttls_before):
                assert (
                    after > before
                ), f"TTL not refreshed for {key}: before={before} after={after}"

        for key, after in zip(keys, afters):
            assert (
                ttl_configured - 2 < after <= ttl_configured
            ), f"TTL for {key}={after}; expected close to {ttl_configured}"

    @pytest.mark.asyncio
    async def test_ttl_refresh_on_action(self):
        # Arrange
        self.created_models = await self._setup_ttl_data()
        model_for_keys = self.created_models[0]
        ttls_before = None
        if self.model_exists_before_action:
            keys = self.all_keys_to_check()
            ttls_before: list[int] = await asyncio.gather(
                *[self.real_redis_client.ttl(k) for k in keys]
            )

        # Act
        with patch.object(
            type(model_for_keys).Meta,
            "refresh_ttl",
            ActionGroup.all(for_ttl=True),
        ):
            await self.perform_action(model_for_keys)

        # Assert
        keys = self.all_keys_to_check()
        ttl_configured = model_for_keys.Meta.ttl
        afters = await asyncio.gather(
            *[self.real_redis_client.ttl(key) for key in keys]
        )
        if self.model_exists_before_action and ttls_before is not None:
            for key, after, before in zip(keys, afters, ttls_before):
                assert (
                    after > before
                ), f"TTL not refreshed for {key}: before={before} after={after}"

        for key, after in zip(keys, afters):
            assert (
                ttl_configured - 2 < after <= ttl_configured
            ), f"TTL for {key}={after}; expected close to {ttl_configured}"

    @pytest.mark.asyncio
    async def test_ttl_no_refresh_on_action(self):
        # Arrange
        self.created_models = await self._setup_ttl_data()
        model_for_keys = self.created_models[0]
        keys = []
        for model in self.created_models:
            keys.extend(self.ttl_keys(model))
        ttls_before = None
        if self.model_exists_before_action:
            ttls_before: list[int] = await asyncio.gather(
                *[self.real_redis_client.ttl(k) for k in keys]
            )

        # Act
        with patch.object(
            type(model_for_keys).Meta,
            "refresh_ttl",
            ActionGroup(0),
        ):
            await self.perform_action(model_for_keys)

        # Assert
        afters = await asyncio.gather(
            *[self.real_redis_client.ttl(key) for key in keys]
        )
        if self.model_exists_before_action and ttls_before is not None:
            for key, after, before in zip(keys, afters, ttls_before):
                assert after <= before, (
                    f"TTL unexpectedly refreshed for {key}: before={before} "
                    f"after={after}"
                )
        for key, after in zip(keys, afters):
            assert (
                0 < after <= REDUCED_TTL_SECONDS
            ), f"TTL for {key}={after}; expected in (0, {REDUCED_TTL_SECONDS}]"

    @pytest.mark.asyncio
    async def test_ttl_update_only_once(self):
        # Arrange
        self.created_models = await self._setup_ttl_data()
        model_for_keys = self.created_models[0]

        flush_spy = AsyncMock()
        redis_expire_spy = AsyncMock()
        pipeline_expire_spy = MagicMock()

        # Act
        with (
            patch.object(type(model_for_keys).Meta, "refresh_ttl", ActionGroup(0)),
            patch.object(actions_module, "flush_action_targets", flush_spy),
            patch.object(Redis, "expire", redis_expire_spy),
            patch.object(Pipeline, "expire", pipeline_expire_spy),
        ):
            await self.perform_action(model_for_keys)

        # Assert
        assert flush_spy.await_count == 1, (
            f"flush_action_targets awaited {flush_spy.await_count} times "
            f"(expected exactly 1) for {type(self).__name__}.perform_action"
        )
        redis_expire_spy.assert_not_awaited()
        pipeline_expire_spy.assert_not_called()

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        cls._prepare_action_test(
            test_attr="test_ttl_refresh_on_action",
            cover_marker=COVER_TTL_REFRESH,
            skip_attr="skip_ttl_refresh",
            parametrize=False,
        )
        cls._prepare_action_test(
            test_attr="test_ttl_no_refresh_on_action",
            cover_marker=COVER_TTL_NO_REFRESH,
            skip_attr="skip_ttl_no_refresh",
            parametrize=False,
        )
        cls._prepare_action_test(
            test_attr="test_ttl_update_only_once",
            cover_marker=COVER_TTL_UPDATE_ONCE,
            skip_attr="skip_ttl_refresh",
            parametrize=False,
        )
        if is_action_for_refresh_sf(cls.covered_method):
            ttl_refresh_base_fn = cls._setup_test_special_field_ttl_refresh
            for adapter in SPECIAL_FIELD_ADAPTERS:
                test_name = (
                    f"test_special_field_ttl_refresh__{adapter.sf_class.__name__}"
                )
                setattr(cls, test_name, ttl_refresh_base_fn)
                cls._prepare_action_test(
                    test_attr=test_name,
                    cover_marker=special_field_cover_marker(
                        adapter.sf_class, SPECIAL_FIELD_TTL_REFRESH
                    ),
                    skip_attr="skip_special_field_ttl",
                    parametrize=False,
                    adapter=adapter,
                )
