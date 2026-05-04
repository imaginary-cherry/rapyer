from benchmarks.base import AsyncBenchmarkTestWithTTL, TTLMode
from benchmarks.models import SimpleListModelWithTTL
from tests.models.collection_types import SimpleListModel


class TestListAppend(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: SimpleListModel,
        TTLMode.TTL: SimpleListModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(items=[])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.aappend("item")


class TestListExtend(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: SimpleListModel,
        TTLMode.TTL: SimpleListModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(items=[])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.aextend(["a", "b", "c"])


class TestListPop(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: SimpleListModel,
        TTLMode.TTL: SimpleListModelWithTTL,
    }
    expected = "item"

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(items=["item"])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.apop()


class TestListInsert(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: SimpleListModel,
        TTLMode.TTL: SimpleListModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(items=["a", "b"])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.ainsert(1, "x")


class TestListClear(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: SimpleListModel,
        TTLMode.TTL: SimpleListModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(items=["a", "b"])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.aclear()
