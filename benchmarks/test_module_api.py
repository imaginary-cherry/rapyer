import rapyer
from benchmarks.base import AsyncBenchmarkTestWithTTL, TTLMode
from benchmarks.models import IntModelWithTTL, StrModelWithTTL
from tests.models.simple_types import IntModel, StrModel


class TestModuleAget(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await rapyer.aget(key)


class TestModuleAfindOneHit(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await rapyer.afind_one(key)


class TestModuleAfindOneMiss(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }
    expected = None

    async def setup(self, mode):
        cls = self.models[mode]
        return f"{cls.__name__}:does-not-exist"

    async def action(self, key):
        return await rapyer.afind_one(key)


class TestModuleAexistsHit(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }
    expected = True

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        return await rapyer.aexists(key)


class TestModuleAexistsMiss(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }
    expected = False

    async def setup(self, mode):
        cls = self.models[mode]
        return f"{cls.__name__}:missing-key"

    async def action(self, key):
        return await rapyer.aexists(key)


class TestModuleAfindSingle(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="test")
        await model.asave()
        return [model.key]

    async def action(self, keys):
        return await rapyer.afind(*keys)


class TestModuleAfindMany(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        models = [cls(name=f"m_{i}") for i in range(10)]
        await rapyer.ainsert(*models)
        return [m.key for m in models]

    async def action(self, keys):
        return await rapyer.afind(*keys)


class TestModuleAfindMixedClasses(AsyncBenchmarkTestWithTTL):
    # Two model classes at once: ``models`` carries the primary, ``_aux_models`` the secondary.
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }
    aux_models = {
        TTLMode.NO_TTL: IntModel,
        TTLMode.TTL: IntModelWithTTL,
    }

    async def setup(self, mode):
        str_cls = self.models[mode]
        int_cls = self.aux_models[mode]
        str_models = [str_cls(name=f"s_{i}") for i in range(5)]
        int_models = [int_cls(count=i) for i in range(5)]
        await rapyer.ainsert(*str_models, *int_models)
        keys = []
        for s, i in zip(str_models, int_models):
            keys.append(s.key)
            keys.append(i.key)
        return keys

    async def action(self, keys):
        return await rapyer.afind(*keys)


class TestModuleAinsertSingle(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        return [cls(name="test")]

    async def action(self, models):
        return await rapyer.ainsert(*models)


class TestModuleAinsertMany(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        return [cls(name=f"m_{i}") for i in range(10)]

    async def action(self, models):
        return await rapyer.ainsert(*models)


class TestModuleAinsertMixedClasses(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }
    aux_models = {
        TTLMode.NO_TTL: IntModel,
        TTLMode.TTL: IntModelWithTTL,
    }

    async def setup(self, mode):
        str_cls = self.models[mode]
        int_cls = self.aux_models[mode]
        str_models = [str_cls(name=f"s_{i}") for i in range(5)]
        int_models = [int_cls(count=i) for i in range(5)]
        return [*str_models, *int_models]

    async def action(self, models):
        return await rapyer.ainsert(*models)


class TestModuleAdeleteManyByKey(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        models = [cls(name=f"del_{i}") for i in range(5)]
        await rapyer.ainsert(*models)
        return [m.key for m in models]

    async def action(self, keys):
        return await rapyer.adelete_many(*keys)


class TestModuleAdeleteManyByModel(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        models = [cls(name=f"del_{i}") for i in range(5)]
        await rapyer.ainsert(*models)
        return models

    async def action(self, models):
        return await rapyer.adelete_many(*models)


class TestModuleApipelineEmpty(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def action(self):
        async with rapyer.apipeline():
            pass


class TestModuleApipelineWithOps(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        async with rapyer.apipeline():
            m = await rapyer.aget(key)
            m.name = "updated"


class TestModuleAlockFromKeyExisting(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="test")
        await model.asave()
        return model.key

    async def action(self, key):
        async with rapyer.alock_from_key(key):
            pass


class TestModuleAlockFromKeyMissing(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        return f"{cls.__name__}:no-such-key"

    async def action(self, key):
        async with rapyer.alock_from_key(key):
            pass
