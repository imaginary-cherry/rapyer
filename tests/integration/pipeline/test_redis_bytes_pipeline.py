from rapyer.types.byte import RedisBytes
from tests.integration.pipeline.pipeline_atomicity_base import PipelineAtomicityBase
from tests.models.simple_types import BytesModel


class TestRedisBytesIadd(PipelineAtomicityBase):
    covered_method = RedisBytes.__iadd__

    async def setup_data(self):
        model = BytesModel(data=b"hello")
        await model.asave()
        return model

    async def perform_action(self, piped):
        piped.data += b" world"

    async def load_data(self):
        loaded = await BytesModel.aget(self.handle.key)
        return loaded.data

    def expected_before(self):
        return b"hello"

    def expected_after(self):
        return b"hello world"
