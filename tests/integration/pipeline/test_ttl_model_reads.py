from rapyer.base import AtomicRedisModel
from rapyer.types.base import RedisType
from tests.integration.pipeline.pipeline_atomicity_base import (
    TTLActionTestBase,
)
from tests.models.collection_types import ComprehensiveTestModel


class TestModelAget(TTLActionTestBase):
    covered_method = AtomicRedisModel.aget
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        model = self.created_models[0]
        await type(model).aget(model.key)


class TestModelAload(TTLActionTestBase):
    covered_method = AtomicRedisModel.aload
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await self.created_models[0].aload()


class TestModelAfind(TTLActionTestBase):
    covered_method = AtomicRedisModel.afind
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await type(self.created_models[0]).afind()


class TestModelAfindOne(TTLActionTestBase):
    covered_method = AtomicRedisModel.afind_one
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await type(self.created_models[0]).afind_one()


class TestRedisTypeAload(ComprehensiveCounterOpBase, TTLActionTestBase):
    covered_method = RedisType.aload
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(counter=42)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await self.created_models[0].counter.aload()

    def expected_before(self):
        return 42

    def expected_after(self):
        return 42
