from benchmarks.base import AsyncBenchmarkTestWithTTL, TTLMode
from benchmarks.models import (
    DirectRedisIntModelWithTTL,
    FloatModelNoTTL,
    FloatModelWithTTL,
)
from tests.models.redis_types import DirectRedisIntModel


class TestIntIncrease(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: DirectRedisIntModel,
        TTLMode.TTL: DirectRedisIntModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(count=0)
        await model.asave()
        return model

    async def action(self, model):
        return await model.count.aincrease(1)


class TestFloatIncrease(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: FloatModelNoTTL,
        TTLMode.TTL: FloatModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(value=0.0)
        await model.asave()
        return model

    async def action(self, model):
        return await model.value.aincrease(1.5)
