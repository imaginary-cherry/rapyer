from benchmarks.base import AsyncBenchmarkTestWithTTL
from rapyer.types.priority_queue import PriorityQueueItem
from tests.models.special_types import PriorityQueueModel

LARGE_PQ_SIZE = 10_000


def _items(n: int) -> list[PriorityQueueItem[str]]:
    return [PriorityQueueItem(value=f"v_{i}", priority=float(i)) for i in range(n)]


class PopulatedPQBenchmark(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (PriorityQueueModel,)

    async def setup(self):
        model = PriorityQueueModel()
        await model.asave()
        await model.tasks.apush_many(_items(LARGE_PQ_SIZE))
        return model


class TestPQPush(PopulatedPQBenchmark):
    async def action(self, model):
        return await model.tasks.apush("new", 0.5)


class TestPQPushMany(PopulatedPQBenchmark):
    extra_items = _items(100)

    async def action(self, model):
        return await model.tasks.apush_many(self.extra_items)


class TestPQPop(PopulatedPQBenchmark):
    async def action(self, model):
        return await model.tasks.apop()


class TestPQPeek(PopulatedPQBenchmark):
    async def action(self, model):
        return await model.tasks.apeek()


class TestPQSize(PopulatedPQBenchmark):
    async def action(self, model):
        return await model.tasks.asize()


class TestPQItems(PopulatedPQBenchmark):
    async def action(self, model):
        return await model.tasks.aitems()


class TestPQRemove(PopulatedPQBenchmark):
    async def action(self, model):
        return await model.tasks.aremove(f"v_{LARGE_PQ_SIZE // 2}")


class TestPQClear(PopulatedPQBenchmark):
    async def action(self, model):
        return await model.tasks.aclear()
