from benchmarks.base import AsyncBenchmarkTestWithTTL
from tests.models.collection_types import ComprehensiveTestModel


class TestPipelineIntIadd(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (ComprehensiveTestModel,)

    async def setup(self):
        model = ComprehensiveTestModel(counter=0, name="test", tags=[], metadata={})
        await model.asave()
        return model

    async def action(self, model):
        async with model.apipeline() as redis_model:
            redis_model.counter += 5


class TestPipelineMultipleOps(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (ComprehensiveTestModel,)

    async def setup(self):
        model = ComprehensiveTestModel(
            counter=0, name="test", tags=["initial"], metadata={"init": "val"}
        )
        await model.asave()
        return model

    async def action(self, model):
        async with model.apipeline() as redis_model:
            redis_model.counter += 1
            redis_model.name += "x"
            redis_model.tags.append("t")
            redis_model.metadata["k"] = "v"
