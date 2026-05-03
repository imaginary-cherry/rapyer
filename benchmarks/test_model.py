from benchmarks.base import AsyncBenchmarkTestWithTTL
from tests.models.index_types import IndexTestModel
from tests.models.simple_types import StrModel


class TestModelSave(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        return StrModel(name="test")

    async def action(self, model):
        return await model.asave()


class TestModelGet(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await StrModel.aget(key)


class TestModelLoad(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aload()


class TestModelUpdate(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aupdate(name="updated")


class TestModelDelete(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.adelete()


class TestModelInsert(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        return [StrModel(name=f"model_{i}") for i in range(3)]

    async def action(self, models):
        return await StrModel.ainsert(*models)


class TestModelFind(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await StrModel.afind(key)


class TestModelDuplicate(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aduplicate()


class TestModelInsertMany(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        return [StrModel(name=f"model_{i}") for i in range(10)]

    async def action(self, models):
        return await StrModel.ainsert(*models)


class TestModelFindWithFilter(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (IndexTestModel,)

    async def setup(self):
        for i in range(5):
            model = IndexTestModel(name=f"user_{i}", age=20 + i, description="test")
            await model.asave()

    async def action(self):
        return await IndexTestModel.afind(IndexTestModel.age >= 22)


class TestModelDeleteMany(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        models = [StrModel(name=f"del_{i}") for i in range(5)]
        await StrModel.ainsert(*models)
        return models

    async def action(self, models):
        return await StrModel.adelete_many(*models)


class TestModelDuplicateMany(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="original")
        await model.asave()
        return model

    async def action(self, model):
        return await model.aduplicate_many(5)
