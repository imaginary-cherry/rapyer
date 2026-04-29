from benchmarks.base import AsyncBenchmarkTestWithTTL
from tests.models.collection_types import SimpleListModel


class TestListAppend(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (SimpleListModel,)

    async def setup(self):
        model = SimpleListModel(items=[])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.aappend("item")


class TestListExtend(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (SimpleListModel,)

    async def setup(self):
        model = SimpleListModel(items=[])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.aextend(["a", "b", "c"])


class TestListPop(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (SimpleListModel,)
    expected = "item"

    async def setup(self):
        model = SimpleListModel(items=["item"])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.apop()


class TestListInsert(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (SimpleListModel,)

    async def setup(self):
        model = SimpleListModel(items=["a", "b"])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.ainsert(1, "x")


class TestListClear(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (SimpleListModel,)

    async def setup(self):
        model = SimpleListModel(items=["a", "b"])
        await model.asave()
        return model

    async def action(self, model):
        return await model.items.aclear()
