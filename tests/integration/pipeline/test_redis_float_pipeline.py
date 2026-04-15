import pytest

from rapyer.types.float import RedisFloat
from tests.integration.pipeline.pipeline_atomicity_base import (
    ActionTestBase,
    BinaryOpCase,
    PipelineAllTypesAmountOpBase,
)
from tests.models.redis_types import PipelineAllTypesTestModel


@pytest.mark.asyncio
async def test_redis_float_operations__changes_outside_pipeline_ignored_sanity():
    # Arrange
    model = PipelineAllTypesTestModel(amount=100.0)
    await model.asave()

    # Act - outside pipeline (should be ignored)
    model.amount += 1000.0
    model.amount *= 5.0

    # Act - inside pipeline (should take effect)
    async with model.apipeline() as m:
        m.amount += 10.0
        m.amount *= 2.0

    # Assert - only pipeline ops applied
    final = await PipelineAllTypesTestModel.aget(model.key)
    assert final.amount == 220.0


class TestRedisFloatAllOperationsCombined(ActionTestBase):
    covered_method = [
        RedisFloat.__iadd__,
        RedisFloat.__isub__,
        RedisFloat.__imul__,
    ]

    def create_models(self):
        return PipelineAllTypesTestModel(amount=100.0)

    async def perform_action(self, piped):
        piped.amount += 50.0
        piped.amount -= 25.0
        piped.amount *= 2.0
        piped.amount /= 5.0
        piped.amount //= 3.0
        piped.amount %= 10.0
        piped.amount **= 2.0

    async def load_data(self):
        loaded = await PipelineAllTypesTestModel.aget(self.created_models.key)
        return loaded.amount

    def expected_before(self):
        return 100.0

    def expected_after(self):
        return 36.0


class TestRedisFloatItruediv(PipelineAllTypesAmountOpBase):
    covered_method = RedisFloat.__itruediv__
    params = [
        BinaryOpCase(100.0, 4.0, 25.0),
        BinaryOpCase(15.0, 2.0, 7.5),
        BinaryOpCase(10.0, 3.0, pytest.approx(3.3333333333333335)),
    ]

    async def perform_action(self, piped):
        piped.amount /= self.test_input.operand


class TestRedisFloatIfloordiv(PipelineAllTypesAmountOpBase):
    covered_method = RedisFloat.__ifloordiv__
    params = [
        BinaryOpCase(17.0, 5.0, 3.0),
        BinaryOpCase(100.5, 7.0, 14.0),
        BinaryOpCase(25.9, 4.0, 6.0),
    ]

    async def perform_action(self, piped):
        piped.amount //= self.test_input.operand


class TestRedisFloatImod(PipelineAllTypesAmountOpBase):
    covered_method = RedisFloat.__imod__
    params = [
        BinaryOpCase(17.5, 5.0, 2.5),
        BinaryOpCase(23.0, 7.0, 2.0),
        BinaryOpCase(100.3, 9.0, pytest.approx(1.3)),
    ]

    async def perform_action(self, piped):
        piped.amount %= self.test_input.operand


class TestRedisFloatIpow(PipelineAllTypesAmountOpBase):
    covered_method = RedisFloat.__ipow__
    params = [
        BinaryOpCase(2.0, 3.0, 8.0),
        BinaryOpCase(3.0, 2.0, 9.0),
        BinaryOpCase(4.0, 0.5, 2.0),
    ]

    async def perform_action(self, piped):
        piped.amount **= self.test_input.operand
