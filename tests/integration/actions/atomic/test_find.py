import rapyer
from rapyer.base import AtomicRedisModel
from rapyer.types.base import RedisType
from tests.integration.actions.comprehensive import ComprehensiveCounterOpBase
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestModelAget(ReadActionTestBase, TTLActionTestBase, UpdateActionTestBase):
    covered_method = AtomicRedisModel.aget
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        model = self.created_models[0]
        return await type(model).aget(model.key)

    def expected_before(self):
        return self.created_models[0]


class TestModelAload(ReadActionTestBase, TTLActionTestBase, UpdateActionTestBase):
    covered_method = AtomicRedisModel.aload
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].aload()

    def expected_before(self):
        return self.created_models[0]


class TestModelAfind(ReadActionTestBase, TTLActionTestBase, UpdateActionTestBase):
    covered_method = AtomicRedisModel.afind
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await type(self.created_models[0]).afind()

    def expected_before(self):
        return [self.created_models[0]]


class TestModelAfindOne(ReadActionTestBase, TTLActionTestBase, UpdateActionTestBase):
    covered_method = AtomicRedisModel.afind_one
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="test", counter=1)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await type(self.created_models[0]).afind_one()

    def expected_before(self):
        return self.created_models[0]


class TestRedisTypeAload(
    ReadActionTestBase, ComprehensiveCounterOpBase, TTLActionTestBase
):
    covered_method = RedisType.aload
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(counter=42)]

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].counter.aload()

    def expected_before(self):
        return 42

    def expected_after(self):
        return 42


class TestRapyerFunctionAget(
    ReadActionTestBase, TTLActionTestBase, UpdateActionTestBase
):
    covered_method = rapyer.aget
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="aget-target")]

    async def perform_action(self, piped):
        return await rapyer.aget(self.created_models[0].key)

    def expected_before(self):
        return self.created_models[0]


class TestRapyerFunctionAfindOne(
    ReadActionTestBase, TTLActionTestBase, UpdateActionTestBase
):
    covered_method = rapyer.afind_one
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="afind-one-target")]

    async def perform_action(self, piped):
        return await rapyer.afind_one(self.created_models[0].key)

    def expected_before(self):
        return self.created_models[0]


class TestRapyerFunctionAfind(
    ReadActionTestBase, TTLActionTestBase, UpdateActionTestBase
):
    covered_method = rapyer.afind
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(name="afind-target")]

    async def perform_action(self, piped):
        return await rapyer.afind(self.created_models[0].key)

    def expected_before(self):
        return [self.created_models[0]]
