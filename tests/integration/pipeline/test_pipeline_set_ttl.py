from rapyer.base import AtomicRedisModel
from tests.integration.pipeline.pipeline_atomicity_base import PipelineAtomicityBase
from tests.models.simple_types import UserModelWithoutTTL

TTL_SECONDS = 300


class TestPipelineAsetTtl(PipelineAtomicityBase):
    """Verify ``aset_ttl`` applied in a pipeline is not flushed until exit."""

    covered_method = AtomicRedisModel.aset_ttl

    async def setup_data(self, **_):
        models = [
            UserModelWithoutTTL(name="user1", age=25),
            UserModelWithoutTTL(name="user2", age=30),
            UserModelWithoutTTL(name="user3", age=35),
        ]
        await UserModelWithoutTTL.ainsert(*models)
        ttls_before = [await self.real_redis_client.ttl(model.key) for model in models]
        assert all(ttl == -1 for ttl in ttls_before)
        return models

    def pipeline_owner(self, handle):
        return handle[0]

    async def perform_action(self, piped, *, handle, **_):
        for model in handle:
            await model.aset_ttl(TTL_SECONDS)

    async def load_data(self, handle):
        return [await self.real_redis_client.ttl(model.key) for model in handle]

    def expected_before(self, **_):
        # All TTLs are still -1 (unset) while the pipeline is open.
        return [-1, -1, -1]

    def assert_after_pipeline(self, loaded, **_):
        # After the pipeline commits, each TTL should be positive and bounded by TTL_SECONDS.
        assert all(0 < ttl <= TTL_SECONDS for ttl in loaded), loaded

    def expected_after(self, **_):
        # Unused because ``assert_after_pipeline`` is overridden with a range check.
        return None
