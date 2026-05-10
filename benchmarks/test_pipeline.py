from datetime import datetime

from benchmarks.base import AsyncBenchmarkTestWithTTL, TTLMode
from tests.models.collection_types import (
    ComprehensiveTestModel,
    ComprehensiveTestModelNoTTL,
)


class TestPipelineIntIadd(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: ComprehensiveTestModelNoTTL,
        TTLMode.TTL: ComprehensiveTestModel,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(counter=0, name="test", tags=[], metadata={})
        await model.asave()
        return model

    async def action(self, model):
        async with model.apipeline() as redis_model:
            redis_model.counter += 5


class TestPipelineMultipleOps(AsyncBenchmarkTestWithTTL):
    models = {
        TTLMode.NO_TTL: ComprehensiveTestModelNoTTL,
        TTLMode.TTL: ComprehensiveTestModel,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(counter=0, name="test", tags=["initial"], metadata={"init": "val"})
        await model.asave()
        return model

    async def action(self, model):
        async with model.apipeline() as redis_model:
            redis_model.counter += 1
            redis_model.name += "x"
            redis_model.tags.append("t")
            redis_model.metadata["k"] = "v"


class TestPipelineMultiAssign(AsyncBenchmarkTestWithTTL):
    """Pipeline body that performs many direct ``=`` field assignments."""

    models = {
        TTLMode.NO_TTL: ComprehensiveTestModelNoTTL,
        TTLMode.TTL: ComprehensiveTestModel,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="initial", counter=0, amount=0.0, data=b"")
        await model.asave()
        return model

    async def action(self, model):
        async with model.apipeline() as redis_model:
            redis_model.name = "new_name"
            redis_model.counter = 42
            redis_model.amount = 3.14
            redis_model.data = b"payload"
            redis_model.event_time = datetime.now()
            redis_model.event_timestamp = datetime.now()


class TestPipelineWithAupdate(AsyncBenchmarkTestWithTTL):
    """Pipeline body that issues ``aupdate`` calls — they defer to the outer pipe."""

    models = {
        TTLMode.NO_TTL: ComprehensiveTestModelNoTTL,
        TTLMode.TTL: ComprehensiveTestModel,
    }

    async def setup(self, mode):
        cls = self.models[mode]
        model = cls(name="initial", counter=0, amount=0.0, data=b"")
        await model.asave()
        return model

    async def action(self, model):
        async with model.apipeline() as redis_model:
            await redis_model.aupdate(
                name="updated",
                counter=42,
                amount=3.14,
                data=b"payload",
            )
            redis_model.data = b"adsfads"
            await redis_model.aupdate(
                event_time=datetime.now(),
                event_timestamp=datetime.now(),
            )
