import rapyer
from benchmarks.base import AsyncBenchmarkTestWithTTL, TTLMode
from benchmarks.models import (
    GenericRedisSetModelNoTTL,
    GenericRedisSetModelWithTTL,
    StrModelWithTTL,
)
from tests.models.simple_types import StrModel

# Kept modest so the benchmark measures round-trip and SF dispatch, not raw set throughput.
SF_MEMBERS = [f"tag_{i}" for i in range(50)]


class TestGetOrCreateCreatedBranch(AsyncBenchmarkTestWithTTL):
    """aget_or_create when the key does NOT exist yet (it writes)."""

    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        # Fresh pk each round → a unique, absent key → always the create path.
        return self._cls(name="test")

    async def action(self, model):
        return await self._cls.aget_or_create(model)


class TestGetOrCreateFoundBranch(AsyncBenchmarkTestWithTTL):
    """aget_or_create when the key already exists (it reads)."""

    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        model = self._cls(name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await self._cls.aget_or_create(model)


class TestModuleGetOrCreateCreatedBranch(AsyncBenchmarkTestWithTTL):
    """Module-level rapyer.aget_or_create on the create branch."""

    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        return self.models[mode](name="test")

    async def action(self, model):
        return await rapyer.aget_or_create(model)


class TestModuleGetOrCreateFoundBranch(AsyncBenchmarkTestWithTTL):
    """Module-level rapyer.aget_or_create on the found branch."""

    models = {
        TTLMode.NO_TTL: StrModel,
        TTLMode.TTL: StrModelWithTTL,
    }

    async def setup(self, mode):
        model = self.models[mode](name="test")
        await model.asave()
        return model

    async def action(self, model):
        return await rapyer.aget_or_create(model)


class TestGetOrCreateCreatedBranchWithSet(AsyncBenchmarkTestWithTTL):
    """
    Create branch with a populated RedisSet: members ship in ARGV and the
    baked-in SF_SAVE snippet persists them in the same round-trip.
    """

    models = {
        TTLMode.NO_TTL: GenericRedisSetModelNoTTL,
        TTLMode.TTL: GenericRedisSetModelWithTTL,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        model = self._cls(name="test")
        # Populate the local mirror only; the create path is what writes it.
        model.tags.update(SF_MEMBERS)
        return model

    async def action(self, model):
        return await self._cls.aget_or_create(model)


class TestGetOrCreateFoundBranchWithSet(AsyncBenchmarkTestWithTTL):
    """
    Found branch with a populated RedisSet: the SF_LOAD snippet returns the
    members in the same round-trip that confirms existence.
    """

    models = {
        TTLMode.NO_TTL: GenericRedisSetModelNoTTL,
        TTLMode.TTL: GenericRedisSetModelWithTTL,
    }

    async def setup(self, mode):
        self._cls = self.models[mode]
        model = self._cls(name="test")
        await model.asave()
        await model.tags.aadd_many(SF_MEMBERS)
        return model

    async def action(self, model):
        return await self._cls.aget_or_create(model)
