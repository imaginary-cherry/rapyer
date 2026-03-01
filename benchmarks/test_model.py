from benchmarks.base import AsyncBenchmarkTest
from tests.models.index_types import IndexTestModel
from tests.models.simple_types import StrModel


class TestModelSave(AsyncBenchmarkTest):
    async def setup(self):
        return StrModel(name="test")

    async def action(self, model):
        return await model.asave()


class TestModelGet(AsyncBenchmarkTest):
    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await StrModel.aget(key)


class TestModelLoad(AsyncBenchmarkTest):
    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aload()


class TestModelUpdate(AsyncBenchmarkTest):
    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aupdate(name="updated")


class TestModelDelete(AsyncBenchmarkTest):
    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.adelete()


class TestModelInsert(AsyncBenchmarkTest):
    async def setup(self):
        return [StrModel(name=f"model_{i}") for i in range(3)]

    async def action(self, models):
        return await StrModel.ainsert(*models)


class TestModelFind(AsyncBenchmarkTest):
    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await StrModel.afind(key)


class TestModelDuplicate(AsyncBenchmarkTest):
    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aduplicate()


class TestModelInsertMany(AsyncBenchmarkTest):
    async def setup(self):
        return [StrModel(name=f"model_{i}") for i in range(10)]

    async def action(self, models):
        return await StrModel.ainsert(*models)


class TestModelFindWithFilter(AsyncBenchmarkTest):
    async def setup(self):
        for i in range(5):
            model = IndexTestModel(name=f"user_{i}", age=20 + i, description="test")
            await model.asave()

    async def action(self):
        return await IndexTestModel.afind(IndexTestModel.age >= 22)


class TestModelDeleteMany(AsyncBenchmarkTest):
    async def setup(self):
        models = [StrModel(name=f"del_{i}") for i in range(5)]
        await StrModel.ainsert(*models)
        return models

    async def action(self, models):
        return await StrModel.adelete_many(*models)


class TestModelDuplicateMany(AsyncBenchmarkTest):
    async def setup(self):
        model = StrModel(name="original")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aduplicate_many(5)
