from benchmarks.base import AsyncBenchmarkTestWithTTL, TTLMode
from benchmarks.models import StrDictModelWithTTL
from tests.models.collection_types import StrDictModel


class TestDictApop(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrDictModel,
        TTLMode.TTL: StrDictModelWithTTL,
    }
    expected = "value"

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.apop("key")


class TestDictApopitem(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrDictModel,
        TTLMode.TTL: StrDictModelWithTTL,
    }
    expected = "value"

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.apopitem()


class TestDictSetItem(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrDictModel,
        TTLMode.TTL: StrDictModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(metadata={})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.aset_item("key", "val")


class TestDictDelItem(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrDictModel,
        TTLMode.TTL: StrDictModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.adel_item("key")


class TestDictUpdate(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrDictModel,
        TTLMode.TTL: StrDictModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(metadata={})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.aupdate(key="value")


class TestDictClear(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrDictModel,
        TTLMode.TTL: StrDictModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(metadata={"key": "value"})
        await model.asave()
        return model

    async def action(self, model):
        return await model.metadata.aclear()
