from rapyer.types.foreign_key import ForeignKey
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.special_types.adapters import SPECIAL_FIELD_ADAPTERS
from tests.models.collection_types import ComprehensiveRefOwner, ComprehensiveTestModel


class TestForeignKeyAfetch(ReadActionTestBase, TTLActionTestBase):
    covered_method = ForeignKey.afetch
    skip_pipeline_atomicity = (
        "afetch returns the resolved target; can't be deferred in a pipeline"
    )
    skip_stale_mirror_in_pipeline = (
        "afetch reads the target via aget; no local mirror to corrupt"
    )

    def create_models(self):
        target = ComprehensiveTestModel(name="resolved", counter=7)
        return [ComprehensiveRefOwner(ref=target), target]

    def ttl_keys(self, model):
        return list(model.all_keys)

    async def populate_special_fields(self, *models):
        target = models[1]
        for adapter in SPECIAL_FIELD_ADAPTERS:
            await adapter.populate(target)

    async def perform_action(self, piped: ComprehensiveRefOwner):
        return await self.created_models[0].ref.afetch()

    def models_to_check_ttl(self):
        # afetch refreshes the fetched target, so its TTL is what we assert.
        return [self.created_models[1]]

    def expected_before(self):
        # afetch returns the hydrated target (the same cached instance).
        return self.created_models[1]
