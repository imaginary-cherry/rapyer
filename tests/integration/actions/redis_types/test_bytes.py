from rapyer.types.byte import RedisBytes
from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestRedisBytesIadd(UpdateActionTestBase):
    covered_method = RedisBytes.__iadd__

    def create_models(self):
        return [ComprehensiveTestModel(data=b"hello")]

    async def perform_action(self, piped):
        piped.data += b" world"

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.data

    def expected_before(self):
        return b"hello"

    def expected_after(self):
        return b"hello world"

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.data += b"_local_marker"

    def get_target_field(self, m: ComprehensiveTestModel) -> bytes:
        return bytes(m.data)
