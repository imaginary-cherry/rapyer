from rapyer.types.byte import RedisBytes
from tests.integration.pipeline.pipeline_atomicity_base import PipelineAtomicityBase
from tests.models.simple_types import BytesModel


class TestRedisBytesIadd(PipelineAtomicityBase):
    covered_method = RedisBytes.__iadd__

    async def setup_data(self, **_):
        model = BytesModel(data=b"hello")
        await model.asave()
        return model

    async def perform_action(self, piped, **_):
        piped.data += b" world"

    async def load_data(self, model):
        loaded = await BytesModel.aget(model.key)
        return loaded.data

    def expected_before(self, **_):
        return b"hello"

    def expected_after(self, **_):
        return b"hello world"
