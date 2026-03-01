from benchmarks.base import AsyncBenchmarkTest
from tests.models.collection_types import SimpleListModel


class TestListAppend(AsyncBenchmarkTest):
    async def setup(self):
        model = SimpleListModel(items=[])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.aappend("item")


class TestListExtend(AsyncBenchmarkTest):
    async def setup(self):
        model = SimpleListModel(items=[])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.aextend(["a", "b", "c"])


class TestListPop(AsyncBenchmarkTest):
    expected = "item"

    async def setup(self):
        model = SimpleListModel(items=["item"])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.apop()


class TestListInsert(AsyncBenchmarkTest):
    async def setup(self):
        model = SimpleListModel(items=["a", "b"])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.ainsert(1, "x")


class TestListClear(AsyncBenchmarkTest):
    async def setup(self):
        model = SimpleListModel(items=["a", "b"])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.aclear()
