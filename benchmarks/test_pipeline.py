from benchmarks.base import AsyncBenchmarkTestWithTTL, TTLMode
from benchmarks.models import ComprehensiveTestModelWithTTL
from tests.models.collection_types import ComprehensiveTestModelNoTTL


class TestPipelineIntIadd(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: ComprehensiveTestModelNoTTL,
        TTLMode.TTL: ComprehensiveTestModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(counter=0, name="test", tags=[], metadata={})
        await model.asave()
        return model

    async def action(self, model):
        async with model.apipeline() as redis_model:
            redis_model.counter += 5


class TestPipelineMultipleOps(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: ComprehensiveTestModelNoTTL,
        TTLMode.TTL: ComprehensiveTestModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(counter=0, name="test", tags=["initial"], metadata={"init": "val"})
        await model.asave()
        return model

    async def action(self, model):
        async with model.apipeline() as redis_model:
            redis_model.counter += 1
            redis_model.name += "x"
            redis_model.tags.append("t")
            redis_model.metadata["k"] = "v"
