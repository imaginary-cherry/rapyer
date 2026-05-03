import rapyer
from benchmarks.base import AsyncBenchmarkTestWithTTL
from tests.models.simple_types import IntModel, StrModel


class TestModuleAget(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await rapyer.aget(key)


class TestModuleAfindOneHit(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await rapyer.afind_one(key)


class TestModuleAfindOneMiss(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)
    expected = None

    async def setup(self):
        return "StrModel:does-not-exist"

    async def action(self, key):
        return await rapyer.afind_one(key)


class TestModuleAexistsHit(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)
    expected = True

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await rapyer.aexists(key)


class TestModuleAexistsMiss(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)
    expected = False

    async def setup(self):
        return "StrModel:missing-key"

    async def action(self, key):
        return await rapyer.aexists(key)


class TestModuleAfindSingle(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return [model.key]

    async def action(self, keys):
        return await rapyer.afind(*keys)


class TestModuleAfindMany(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        models = [StrModel(name=f"m_{i}") for i in range(10)]
        await rapyer.ainsert(*models)
        return [m.key for m in models]

    async def action(self, keys):
        return await rapyer.afind(*keys)


class TestModuleAfindMixedClasses(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel, IntModel)

    async def setup(self):
        str_models = [StrModel(name=f"s_{i}") for i in range(5)]
        int_models = [IntModel(count=i) for i in range(5)]
        await rapyer.ainsert(*str_models, *int_models)
        keys = []
        for s, i in zip(str_models, int_models):
            keys.append(s.key)
            keys.append(i.key)
        return keys

    async def action(self, keys):
        return await rapyer.afind(*keys)


class TestModuleAinsertSingle(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        return [StrModel(name="test")]

    async def action(self, models):
        return await rapyer.ainsert(*models)


class TestModuleAinsertMany(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        return [StrModel(name=f"m_{i}") for i in range(10)]

    async def action(self, models):
        return await rapyer.ainsert(*models)


class TestModuleAinsertMixedClasses(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel, IntModel)

    async def setup(self):
        str_models = [StrModel(name=f"s_{i}") for i in range(5)]
        int_models = [IntModel(count=i) for i in range(5)]
        return [*str_models, *int_models]

    async def action(self, models):
        return await rapyer.ainsert(*models)


class TestModuleAdeleteManyByKey(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        models = [StrModel(name=f"del_{i}") for i in range(5)]
        await rapyer.ainsert(*models)
        return [m.key for m in models]

    async def action(self, keys):
        return await rapyer.adelete_many(*keys)


class TestModuleAdeleteManyByModel(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        models = [StrModel(name=f"del_{i}") for i in range(5)]
        await rapyer.ainsert(*models)
        return models

    async def action(self, models):
        return await rapyer.adelete_many(*models)


class TestModuleApipelineEmpty(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def action(self):
        async with rapyer.apipeline():
            pass


class TestModuleApipelineWithOps(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        async with rapyer.apipeline():
            m = await rapyer.aget(key)
            m.name = "updated"


class TestModuleAlockFromKeyExisting(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        model = StrModel(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        async with rapyer.alock_from_key(key):
            pass


class TestModuleAlockFromKeyMissing(AsyncBenchmarkTestWithTTL):
    models_for_ttl = (StrModel,)

    async def setup(self):
        return "StrModel:no-such-key"

    async def action(self, key):
        async with rapyer.alock_from_key(key):
            pass
