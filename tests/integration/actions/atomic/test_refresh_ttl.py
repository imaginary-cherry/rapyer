from rapyer.base import AtomicRedisModel
from tests.integration.actions.base import ActionTestBase
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

    async def setup_data(self):
        models = await super().setup_data()
        model = models[0]
        # Lower the TTL so there's a measurable gap to refresh.
        await self.real_redis_client.expire(model.key, self.reduced_ttl)
        ttl_before = await self.real_redis_client.ttl(model.key)
        assert 0 < ttl_before <= self.reduced_ttl
        return models

    async def perform_action(self, piped):
        await self.created_models[0].refresh_ttl_if_needed(can_use_pipeline=True)

    async def load_data(self):
        return await self.real_redis_client.ttl(self.created_models[0].key)

    def assert_during_pipeline(self, loaded):
        assert loaded <= self.reduced_ttl

    async def assert_after_pipeline(self, loaded):
        assert self.reduced_ttl < loaded <= TTL_REFRESH_TEST_SECONDS
