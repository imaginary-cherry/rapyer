import rapyer
from benchmarks.base import AsyncBenchmarkTestWithTTL, TTLMode
from benchmarks.models import IntModelWithTTL
from tests.models.collection_types import ComprehensiveTestModel, ComprehensiveTestModelNoTTL
from tests.models.simple_types import IntModel

NUM_MODELS = 100


class TestMultiModelPipelineIntIncrement(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: IntModel,
        TTLMode.TTL: IntModelWithTTL,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        models = [self._cls(count=0, score=100) for _ in range(NUM_MODELS)]
        await self._cls.ainsert(*models)
        return models

    async def action(self, models):
        async with rapyer.apipeline():
            for model in models:
                loaded = await self._cls.aget(model.key)
                loaded.count += 1


class TestMultiModelPipelineStrSet(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: ComprehensiveTestModelNoTTL,
        TTLMode.TTL: ComprehensiveTestModel,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        models = [
            self._cls(counter=0, name="test", tags=[], metadata={})
            for _ in range(NUM_MODELS)
        ]
        await self._cls.ainsert(*models)
        return models

    async def action(self, models):
        async with rapyer.apipeline():
            for model in models:
                loaded = await self._cls.aget(model.key)
                loaded.name = "updated"


class TestMultiModelPipelineMixedOps(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: ComprehensiveTestModelNoTTL,
        TTLMode.TTL: ComprehensiveTestModel,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        models = [
            self._cls(
                counter=0, name="test", tags=["initial"], metadata={"init": "val"}
            )
            for _ in range(NUM_MODELS)
        ]
        await self._cls.ainsert(*models)
        return models

    async def action(self, models):
        async with rapyer.apipeline():
            for model in models:
                loaded = await self._cls.aget(model.key)
                loaded.counter += 1
                loaded.name += "x"
                loaded.tags.append("t")
                loaded.metadata["k"] = "v"
