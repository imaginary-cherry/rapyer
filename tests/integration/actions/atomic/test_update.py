from rapyer.base import AtomicRedisModel
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestRapyerAupdate(UpdateActionTestBase, TTLActionTestBase):
    """After aupdate was switched to ``ensure_pipeline``, it defers to an outer
    pipeline like every other mutation."""

    covered_method = AtomicRedisModel.aupdate

    def create_models(self):
        return [ComprehensiveTestModel(name="original", counter=10)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await self.created_models[0].aupdate(name="updated", counter=99)

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.name, loaded.counter

    def expected_before(self):
        return "original", 10

    def expected_after(self):
        return "updated", 99
