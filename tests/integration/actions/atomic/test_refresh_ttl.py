from rapyer.base import AtomicRedisModel
from tests.integration.actions.base import ActionTestBase
from tests.integration.special_types.adapters import SPECIAL_FIELD_ADAPTERS
from tests.models.collection_types import (
    TTL_REFRESH_TEST_SECONDS,
    ComprehensiveTestModel,
)


class TestRapyerRefreshTtl(ActionTestBase):
    covered_method = AtomicRedisModel.refresh_ttl_if_needed
    skip_stale_mirror_in_pipeline = (
        "TTL primitive; no field-level local mirror to corrupt"
    )
    reduced_ttl: int = 10

    def create_models(self):
        return [ComprehensiveTestModel(name="ttl_test", counter=25)]

    def all_keys(self) -> list[str]:
        # Every key ``refresh_ttl`` touches: the model key plus each special-field
        # key, sourced from the adapters (``tasks``, ``container.labels``,
        # ``container.tasks``).
        model = self.created_models[0]
        keys = [model.key]
        for adapter in SPECIAL_FIELD_ADAPTERS:
            keys.extend(adapter.additional_ttl_keys(model))
        return keys

    async def setup_data(self):
        models = await super().setup_data()
        self.created_models = models
        # Lower every key's TTL (model + special fields) so there's a measurable
        # gap to refresh.
        for key in self.all_keys():
            await self.real_redis_client.expire(key, self.reduced_ttl)
        ttls_before = [await self.real_redis_client.ttl(k) for k in self.all_keys()]
        assert all(0 < ttl <= self.reduced_ttl for ttl in ttls_before), ttls_before
        return models

    async def perform_action(self, piped):
        await self.created_models[0].refresh_ttl_if_needed(can_use_pipeline=True)

    async def load_data(self):
        return [await self.real_redis_client.ttl(k) for k in self.all_keys()]

    def assert_during_pipeline(self, loaded):
        assert all(ttl <= self.reduced_ttl for ttl in loaded), loaded

    async def assert_after_pipeline(self, loaded):
        assert all(
            self.reduced_ttl < ttl <= TTL_REFRESH_TEST_SECONDS for ttl in loaded
        ), loaded
