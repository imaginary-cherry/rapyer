from benchmarks.base import AsyncBenchmarkTest
from tests.models.collection_types import StrDictModel


class TestDictApop(AsyncBenchmarkTest):
    expected = "value"

    async def setup(self):
        model = StrDictModel(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.apop("key")


class TestDictApopitem(AsyncBenchmarkTest):
    expected = "value"

    async def setup(self):
        model = StrDictModel(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.apopitem()


class TestDictSetItem(AsyncBenchmarkTest):
    async def setup(self):
        model = StrDictModel(metadata={})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.aset_item("key", "val")


class TestDictDelItem(AsyncBenchmarkTest):
    async def setup(self):
        model = StrDictModel(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.adel_item("key")


class TestDictUpdate(AsyncBenchmarkTest):
    async def setup(self):
        model = StrDictModel(metadata={})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.aupdate(key="value")


class TestDictClear(AsyncBenchmarkTest):
    async def setup(self):
        model = StrDictModel(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.aclear()
