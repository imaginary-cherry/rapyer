from rapyer.base import AtomicRedisModel
from tests.integration.actions.base import ActionTestBase
from tests.models.collection_types import ComprehensiveTestModelNoTTL

TTL_SECONDS = 300


class TestRapyerAsetTtl(ActionTestBase):
    covered_method = AtomicRedisModel.aset_ttl

    def create_models(self):
        return [
            ComprehensiveTestModelNoTTL(name="user1", counter=25),
            ComprehensiveTestModelNoTTL(name="user2", counter=30),
            ComprehensiveTestModelNoTTL(name="user3", counter=35),
        ]

    async def setup_data(self):
        models = await super().setup_data()
        ttls_before = [await self.real_redis_client.ttl(m.key) for m in models]
        assert all(ttl == -1 for ttl in ttls_before)
        return models

    async def perform_action(self, piped):
        for m in self.created_models:
            await m.aset_ttl(TTL_SECONDS)

    async def load_data(self):
        return [await self.real_redis_client.ttl(m.key) for m in self.created_models]

    def expected_before(self):
        return [-1, -1, -1]

    def assert_after_pipeline(self, loaded):
        assert all(0 < ttl <= TTL_SECONDS for ttl in loaded), loaded


class TestAsetTtl(ActionTestBase):
    """Verify ``aset_ttl`` applied in a pipeline is not flushed until exit."""

    covered_method = AtomicRedisModel.aset_ttl

    def create_models(self):
        return [
            ComprehensiveTestModelNoTTL(name="user1", counter=25),
            ComprehensiveTestModelNoTTL(name="user2", counter=30),
            ComprehensiveTestModelNoTTL(name="user3", counter=35),
        ]

    async def setup_data(self):
        models = await super().setup_data()
        ttls_before = [await self.real_redis_client.ttl(model.key) for model in models]
        assert all(ttl == -1 for ttl in ttls_before)
        return models

    async def perform_action(self, piped):
        for model in self.created_models:
            await model.aset_ttl(TTL_SECONDS)

    async def load_data(self):
        return [await self.real_redis_client.ttl(model.key) for model in self.created_models]

    def expected_before(self):
        # All TTLs are still -1 (unset) while the pipeline is open.
        return [-1, -1, -1]

    def assert_after_pipeline(self, loaded):
        # After the pipeline commits, each TTL should be positive and bounded by TTL_SECONDS.
        assert all(0 < ttl <= TTL_SECONDS for ttl in loaded), loaded
