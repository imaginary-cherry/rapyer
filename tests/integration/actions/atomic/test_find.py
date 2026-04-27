import rapyer
from rapyer.base import AtomicRedisModel
from rapyer.types.base import RedisType
from tests.integration.actions.comprehensive_counter import ComprehensiveCounterOpBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestModelAget(TTLActionTestBase, UpdateActionTestBase):
    covered_method = AtomicRedisModel.aget
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        model = self.created_models[0]
        await type(model).aget(model.key)


class TestModelAload(TTLActionTestBase, UpdateActionTestBase):
    covered_method = AtomicRedisModel.aload
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await self.created_models[0].aload()


class TestModelAfind(TTLActionTestBase, UpdateActionTestBase):
    covered_method = AtomicRedisModel.afind
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await type(self.created_models[0]).afind()


class TestModelAfindOne(TTLActionTestBase, UpdateActionTestBase):
    covered_method = AtomicRedisModel.afind_one
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await type(self.created_models[0]).afind_one()


class TestRedisTypeAload(ComprehensiveCounterOpBase, TTLActionTestBase):
    covered_method = RedisType.aload
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(counter=42)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await self.created_models[0].counter.aload()

    def expected_before(self):
        return 42

    def expected_after(self):
        return 42


class TestRapyerFunctionAget(TTLActionTestBase, UpdateActionTestBase):
    covered_method = rapyer.aget
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="aget-target")]

    async def perform_action(self, piped):
        assert await rapyer.aget(self.created_models[0].key) is not None


class TestRapyerFunctionAfindOne(TTLActionTestBase, UpdateActionTestBase):
    covered_method = rapyer.afind_one
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="afind-one-target")]

    async def perform_action(self, piped):
        assert await rapyer.afind_one(self.created_models[0].key) is not None


class TestRapyerFunctionAfind(TTLActionTestBase, UpdateActionTestBase):
    covered_method = rapyer.afind
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="afind-target")]

    async def perform_action(self, piped):
        results = await rapyer.afind(self.created_models[0].key)
        assert len(results) == 1
