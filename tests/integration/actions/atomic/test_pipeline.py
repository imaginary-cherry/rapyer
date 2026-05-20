import rapyer
from rapyer.base import AtomicRedisModel
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestModelApipeline(TTLActionTestBase, UpdateActionTestBase):
    covered_method = AtomicRedisModel.apipeline
    skip_stale_mirror_in_pipeline = "apipeline is the pipeline mechanism itself; no field-level local mirror to corrupt"

    def create_models(self):
        return [ComprehensiveTestModel(name="original")]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        async with piped.apipeline(use_existing_pipe=True) as model:
            model.name = "updated"

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.name

    def expected_before(self):
        return "original"

    def expected_after(self):
        return "updated"

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.name += "_local_marker"

    def get_target_field(self, m: ComprehensiveTestModel) -> str:
        return str(m.name)


class TestRapyerFunctionApipeline(TTLActionTestBase, UpdateActionTestBase):
    covered_method = rapyer.apipeline
    skip_ttl_refresh = "Apipeline doesn't refresh ttl on its own as an action"
    skip_special_field_ttl = "Apipeline doesn't refresh ttl on its own as an action"
    skip_stale_mirror_in_pipeline = "apipeline is the pipeline mechanism itself; no field-level local mirror to corrupt"

    def create_models(self):
        return [ComprehensiveTestModel(name="original")]

    async def perform_action(self, piped):
        async with rapyer.apipeline(use_existing_pipe=True):
            piped.name = "updated"

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.name

    def expected_before(self):
        return "original"

    def expected_after(self):
        return "updated"

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.name += "_local_marker"

    def get_target_field(self, m: ComprehensiveTestModel) -> str:
        return str(m.name)
