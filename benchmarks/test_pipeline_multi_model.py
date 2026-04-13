import rapyer
from benchmarks.base import AsyncBenchmarkTest
from tests.models.collection_types import ComprehensiveTestModel
from tests.models.simple_types import IntModel

NUM_MODELS = 100


class TestMultiModelPipelineIntIncrement(AsyncBenchmarkTest):
    async def setup(self):
        models = [IntModel(count=0, score=100) for _ in range(NUM_MODELS)]
        await IntModel.ainsert(*models)
        return models

    async def action(self, models):
        async with rapyer.apipeline():
            for model in models:
                loaded = await IntModel.aget(model.key)
                loaded.count += 1


class TestMultiModelPipelineStrSet(AsyncBenchmarkTest):
    async def setup(self):
        models = [
            ComprehensiveTestModel(counter=0, name="test", tags=[], metadata={})
            for _ in range(NUM_MODELS)
        ]
        await ComprehensiveTestModel.ainsert(*models)
        return models

    async def action(self, models):
        async with rapyer.apipeline():
            for model in models:
                loaded = await ComprehensiveTestModel.aget(model.key)
                loaded.name = "updated"


class TestMultiModelPipelineMixedOps(AsyncBenchmarkTest):
    async def setup(self):
        models = [
            ComprehensiveTestModel(
                counter=0, name="test", tags=["initial"], metadata={"init": "val"}
            )
            for _ in range(NUM_MODELS)
        ]
        await ComprehensiveTestModel.ainsert(*models)
        return models

    async def action(self, models):
        async with rapyer.apipeline():
            for model in models:
                loaded = await ComprehensiveTestModel.aget(model.key)
                loaded.counter += 1
                loaded.name += "x"
                loaded.tags.append("t")
                loaded.metadata["k"] = "v"
