from benchmarks.base import AsyncBenchmarkTestWithTTL
from tests.models.redis_types import DirectRedisIntModel
from tests.models.simple_types import FloatModel


class TestIntIncrease(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (DirectRedisIntModel,)

    async def setup(self):
        model = DirectRedisIntModel(count=0)
        await model.asave()
        return model

    async def action(self, model):
        return await model.count.aincrease(1)


class TestFloatIncrease(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (FloatModel,)

    async def setup(self):
        model = FloatModel(value=0.0)
        await model.asave()
        return model

    async def action(self, model):
        return await model.value.aincrease(1.5)
