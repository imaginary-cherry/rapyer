from benchmarks.base import AsyncBenchmarkTestWithTTL
from tests.models.collection_types import StrDictModel


class TestDictApop(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrDictModel,)
    expected = "value"

    async def setup(self):
        model = StrDictModel(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.apop("key")


class TestDictApopitem(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrDictModel,)
    expected = "value"

    async def setup(self):
        model = StrDictModel(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.apopitem()


class TestDictSetItem(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrDictModel,)

    async def setup(self):
        model = StrDictModel(metadata={})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.aset_item("key", "val")


class TestDictDelItem(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrDictModel,)

    async def setup(self):
        model = StrDictModel(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.adel_item("key")


class TestDictUpdate(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrDictModel,)

    async def setup(self):
        model = StrDictModel(metadata={})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.aupdate(key="value")


class TestDictClear(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrDictModel,)

    async def setup(self):
        model = StrDictModel(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.aclear()
