from rapyer.types.base import RedisType
from rapyer.types.string import RedisStr
from tests.integration.actions.base import BinaryOpCase
from tests.integration.actions.comprehensive_name import ComprehensiveNameOpBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestRedisStrAllOperationsCombined(ComprehensiveNameOpBase):
    covered_method = RedisStr.__iadd__

    def create_models(self):
        return [ComprehensiveTestModel(name="hello")]

    async def perform_action(self, piped):
        piped.name += "_world"
        piped.name += "_test"

    def expected_before(self):
        return "hello"

    def expected_after(self):
        return "hello_world_test"


class TestRedisStrImul(ComprehensiveNameOpBase):
    covered_method = RedisStr.__imul__
    params = [BinaryOpCase("test", 0, "")]

    def create_models(self):
        return [ComprehensiveTestModel(name=self.test_input.initial)]

    async def perform_action(self, piped):
        piped.name *= self.test_input.operand

    def expected_before(self):
        return self.test_input.initial

    def expected_after(self):
        return self.test_input.expected


class TestStringSet(UpdateActionTestBase, TTLActionTestBase):
    covered_method = RedisType.asave

    def create_models(self):
        return [ComprehensiveTestModel(name="original")]

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.name = "updated"
        await piped.name.asave()

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.name

    def expected_before(self):
        return "original"

    def expected_after(self):
        return "updated"
