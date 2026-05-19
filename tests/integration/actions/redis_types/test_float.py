import pytest

from rapyer.types.float import RedisFloat
from tests.integration.actions.base import BinaryOpCase
from tests.integration.actions.comprehensive import ComprehensiveAmountOpBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestRedisFloatAllOperationsCombined(UpdateActionTestBase):
    covered_method = [
        RedisFloat.__iadd__,
        RedisFloat.__isub__,
        RedisFloat.__imul__,
    ]

    def create_models(self):
        return [ComprehensiveTestModel(amount=100.0)]

    async def perform_action(self, piped):
        piped.amount += 50.0
        piped.amount -= 25.0
        piped.amount *= 2.0
        piped.amount /= 5.0
        piped.amount //= 3.0
        piped.amount %= 10.0
        piped.amount **= 2.0

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.amount

    def expected_before(self):
        return 100.0

    def expected_after(self):
        return 36.0

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.amount += 1.2345e-5

    def get_target_field(self, m: ComprehensiveTestModel) -> float:
        return float(m.amount)


class TestFloatAincrease(UpdateActionTestBase, TTLActionTestBase):
    covered_method = RedisFloat.aincrease

    def create_models(self):
        return [ComprehensiveTestModel(amount=50.0)]

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.amount

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.amount.aincrease(10.5)

    def expected_before(self):
        return 50.0

    def expected_after(self):
        return 60.5

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.amount += 1.2345e-5

    def get_target_field(self, m: ComprehensiveTestModel) -> float:
        return float(m.amount)


class TestRedisFloatItruediv(ComprehensiveAmountOpBase):
    covered_method = RedisFloat.__itruediv__
    params = [
        BinaryOpCase(100.0, 4.0, 25.0),
        BinaryOpCase(15.0, 2.0, 7.5),
        BinaryOpCase(10.0, 3.0, pytest.approx(3.3333333333333335)),
    ]

    async def perform_action(self, piped):
        piped.amount /= self.test_input.operand


class TestRedisFloatIfloordiv(ComprehensiveAmountOpBase):
    covered_method = RedisFloat.__ifloordiv__
    params = [
        BinaryOpCase(17.0, 5.0, 3.0),
        BinaryOpCase(100.5, 7.0, 14.0),
        BinaryOpCase(25.9, 4.0, 6.0),
    ]

    async def perform_action(self, piped):
        piped.amount //= self.test_input.operand


class TestRedisFloatImod(ComprehensiveAmountOpBase):
    covered_method = RedisFloat.__imod__
    params = [
        BinaryOpCase(17.5, 5.0, 2.5),
        BinaryOpCase(23.0, 7.0, 2.0),
        BinaryOpCase(100.3, 9.0, pytest.approx(1.3)),
    ]

    async def perform_action(self, piped):
        piped.amount %= self.test_input.operand


class TestRedisFloatIpow(ComprehensiveAmountOpBase):
    covered_method = RedisFloat.__ipow__
    params = [
        BinaryOpCase(2.0, 3.0, 8.0),
        BinaryOpCase(3.0, 2.0, 9.0),
        BinaryOpCase(4.0, 0.5, 2.0),
    ]

    async def perform_action(self, piped):
        piped.amount **= self.test_input.operand
