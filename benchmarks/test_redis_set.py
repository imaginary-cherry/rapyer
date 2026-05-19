from benchmarks.base import AsyncBenchmarkTestWithTTL, TTLMode
from benchmarks.models import GenericRedisSetModelNoTTL, GenericRedisSetModelWithTTL

POPULATED_SET_SIZE = 1_000


def _members(n: int) -> list[str]:
    return [f"v_{i}" for i in range(n)]


class PopulatedSetBenchmark(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: GenericRedisSetModelNoTTL,
        TTLMode.TTL: GenericRedisSetModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls()
        await model.asave()
        await model.tags.aadd_many(_members(POPULATED_SET_SIZE))
        return model


class TwoPopulatedSetsBenchmark(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: GenericRedisSetModelNoTTL,
        TTLMode.TTL: GenericRedisSetModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model_a = cls(name="a")
        model_b = cls(name="b")
        await model_a.asave()
        await model_b.asave()
        await model_a.tags.aadd_many(_members(POPULATED_SET_SIZE))
        # Overlapping range so SINTER/SDIFF have non-trivial output.
        await model_b.tags.aadd_many(
            [f"v_{i}" for i in range(POPULATED_SET_SIZE // 2, POPULATED_SET_SIZE * 3 // 2)]
        )
        return model_a, model_b


class TestSetAdd(PopulatedSetBenchmark):
    async def action(self, model):
        return await model.tags.aadd("new")


class TestSetAddMany(PopulatedSetBenchmark):
    extra_members = _members(100)

    async def action(self, model):
        return await model.tags.aadd_many(self.extra_members)


class TestSetRemove(PopulatedSetBenchmark):
    async def action(self, model):
        return await model.tags.aremove(f"v_{POPULATED_SET_SIZE // 2}")


class TestSetContainsHit(PopulatedSetBenchmark):
    async def action(self, model):
        return await model.tags.acontains(f"v_{POPULATED_SET_SIZE // 2}")


class TestSetContainsMiss(PopulatedSetBenchmark):
    async def action(self, model):
        return await model.tags.acontains("missing")


class TestSetSize(PopulatedSetBenchmark):
    async def action(self, model):
        return await model.tags.asize()


class TestSetMembers(PopulatedSetBenchmark):
    async def action(self, model):
        return await model.tags.amembers()


class TestSetClear(PopulatedSetBenchmark):
    async def action(self, model):
        return await model.tags.aclear()


class TestSetUnion(TwoPopulatedSetsBenchmark):
    async def action(self, pair):
        set_a, set_b = pair
        return await set_a.tags.aunion(set_b.tags)


class TestSetIntersect(TwoPopulatedSetsBenchmark):
    async def action(self, pair):
        set_a, set_b = pair
        return await set_a.tags.aintersect(set_b.tags)


class TestSetDifference(TwoPopulatedSetsBenchmark):
    async def action(self, pair):
        set_a, set_b = pair
        return await set_a.tags.adifference(set_b.tags)
