from rapyer.types.byte import RedisBytes
from tests.integration.pipeline.pipeline_atomicity_base import ActionTestBase
from tests.models.simple_types import BytesModel


class TestRedisBytesIadd(ActionTestBase):
    covered_method = RedisBytes.__iadd__

    def create_models(self):
        return BytesModel(data=b"hello")

    async def perform_action(self, piped):
        piped.data += b" world"

    async def load_data(self):
        loaded = await BytesModel.aget(self.created_models.key)
        return loaded.data

    def expected_before(self):
        return b"hello"

    def expected_after(self):
        return b"hello world"
