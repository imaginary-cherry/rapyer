from benchmarks.base import AsyncBenchmarkTest
from tests.models.redis_types import DirectRedisIntModel
from tests.models.simple_types import FloatModel


class TestIntIncrease(AsyncBenchmarkTest):
    async def setup(self):
        model = DirectRedisIntModel(count=0)
        await model.asave()
        return model

    async def action(self, model):
        return await model.count.aincrease(1)


class TestFloatIncrease(AsyncBenchmarkTest):
    async def setup(self):
        model = FloatModel(value=0.0)
        await model.asave()
        return model

    async def action(self, model):
        return await model.value.aincrease(1.5)
