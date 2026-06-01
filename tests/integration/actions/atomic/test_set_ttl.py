from rapyer.base import AtomicRedisModel
from tests.integration.actions.base import ActionTestBase
from tests.integration.special_types.adapters import SPECIAL_FIELD_ADAPTERS
from tests.models.collection_types import ComprehensiveTestModelNoTTL

TTL_SECONDS = 300


def _all_ttl_keys(models) -> list[str]:
    """Every key ``aset_ttl`` touches: each model's main key plus its
    special-field keys, sourced from the special-field adapters (``tasks``,
    ``container.labels``, ``container.tasks``)."""
    keys: list[str] = []
    for model in models:
        keys.append(model.key)
        for adapter in SPECIAL_FIELD_ADAPTERS:
            keys.extend(adapter.additional_ttl_keys(model))
    return keys


class TestRapyerAsetTtl(ActionTestBase):
    covered_method = AtomicRedisModel.aset_ttl
    skip_stale_mirror_in_pipeline = (
        "TTL primitive; no field-level local mirror to corrupt"
    )

    def create_models(self):
        return [
            ComprehensiveTestModelNoTTL(name="user1", counter=25),
            ComprehensiveTestModelNoTTL(name="user2", counter=30),
            ComprehensiveTestModelNoTTL(name="user3", counter=35),
        ]

    async def setup_data(self):
        models = await super().setup_data()
        self.created_models = models
        ttls_before = [
            await self.real_redis_client.ttl(k) for k in _all_ttl_keys(models)
        ]
        assert all(ttl == -1 for ttl in ttls_before), ttls_before
        return models

    async def perform_action(self, piped):
        for m in self.created_models:
            await m.aset_ttl(TTL_SECONDS)

    async def load_data(self):
        return [
            await self.real_redis_client.ttl(k)
            for k in _all_ttl_keys(self.created_models)
        ]

    def expected_before(self):
        return [-1] * len(_all_ttl_keys(self.created_models))

    async def assert_after_pipeline(self, loaded):
        assert all(0 < ttl <= TTL_SECONDS for ttl in loaded), loaded


class TestAsetTtl(ActionTestBase):
    """Verify ``aset_ttl`` applied in a pipeline is not flushed until exit."""

    covered_method = AtomicRedisModel.aset_ttl
    skip_stale_mirror_in_pipeline = (
        "TTL primitive; no field-level local mirror to corrupt"
    )

    def create_models(self):
        return [
            ComprehensiveTestModelNoTTL(name="user1", counter=25),
            ComprehensiveTestModelNoTTL(name="user2", counter=30),
            ComprehensiveTestModelNoTTL(name="user3", counter=35),
        ]

    async def setup_data(self):
        models = await super().setup_data()
        self.created_models = models
        ttls_before = [
            await self.real_redis_client.ttl(k) for k in _all_ttl_keys(models)
        ]
        assert all(ttl == -1 for ttl in ttls_before), ttls_before
        return models

    async def perform_action(self, piped):
        for model in self.created_models:
            await model.aset_ttl(TTL_SECONDS)

    async def load_data(self):
        return [
            await self.real_redis_client.ttl(k)
            for k in _all_ttl_keys(self.created_models)
        ]

    def expected_before(self):
        # Every key (model + special fields) is still unset while the pipeline
        # is open.
        return [-1] * len(_all_ttl_keys(self.created_models))

    async def assert_after_pipeline(self, loaded):
        # After the pipeline commits, each TTL should be positive and bounded.
        assert all(0 < ttl <= TTL_SECONDS for ttl in loaded), loaded
