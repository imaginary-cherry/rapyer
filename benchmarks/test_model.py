from benchmarks.base import AsyncBenchmarkTestWithTTL, TTLMode
from benchmarks.models import IndexTestModelWithTTL, StrModelWithTTL
from tests.models.index_types import IndexTestModel
from tests.models.simple_types import StrModel


class TestModelSave(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        return cls(name="test")

    async def action(self, model):
        return await model.asave()


class TestModelGet(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        model = self._cls(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await self._cls.aget(key)


class TestModelLoad(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aload()


class TestModelUpdate(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aupdate(name="updated")


class TestModelDelete(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.adelete()


class TestModelInsert(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        return [self._cls(name=f"model_{i}") for i in range(3)]

    async def action(self, models):
        return await self._cls.ainsert(*models)


class TestModelFind(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        model = self._cls(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await self._cls.afind(key)


class TestModelDuplicate(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aduplicate()


class TestModelInsertMany(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        return [self._cls(name=f"model_{i}") for i in range(10)]

    async def action(self, models):
        return await self._cls.ainsert(*models)


class TestModelFindWithFilter(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: IndexTestModel,
        TTLMode.TTL: IndexTestModelWithTTL,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        for i in range(5):
            model = self._cls(name=f"user_{i}", age=20 + i, description="test")
            await model.asave()

    async def action(self):
        return await self._cls.afind(self._cls.age >= 22)


class TestModelDeleteMany(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        models = [self._cls(name=f"del_{i}") for i in range(5)]
        await self._cls.ainsert(*models)
        return models

    async def action(self, models):
        return await self._cls.adelete_many(*models)


class TestModelDuplicateMany(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="original")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aduplicate_many(5)
