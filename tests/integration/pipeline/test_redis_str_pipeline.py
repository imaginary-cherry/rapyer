import pytest

from rapyer.types.string import RedisStr
from tests.integration.pipeline.pipeline_atomicity_base import (
    BinaryOpCase,
    PipelineAllTypesNameOpBase,
)
from tests.models.redis_types import PipelineAllTypesTestModel


class TestRedisStrAllOperationsCombined(PipelineAllTypesNameOpBase):
    covered_method = RedisStr.__iadd__

    async def setup_data(self):
        model = PipelineAllTypesTestModel(name="hello")
        await model.asave()
        return model

    async def perform_action(self, piped):
        piped.name += "_world"
        piped.name += "_test"

    def expected_before(self):
        return "hello"

    def expected_after(self):
        return "hello_world_test"


@pytest.mark.asyncio
async def test_redis_str_operations__changes_outside_pipeline_ignored_sanity():
    # Arrange
    model = PipelineAllTypesTestModel(name="hello")
    await model.asave()

    # Act - outside pipeline (should be ignored)
    model.name += "_outside"
    model.name += "_ignored"

    # Act - inside pipeline (should take effect)
    async with model.apipeline() as m:
        m.name += "_inside"

    # Assert - only pipeline ops applied
    final = await PipelineAllTypesTestModel.aget(model.key)
    assert final.name == "hello_inside"


class TestRedisStrImul(PipelineAllTypesNameOpBase):
    covered_method = RedisStr.__imul__
    params = [BinaryOpCase("test", 0, "")]

    async def setup_data(self):
        model = PipelineAllTypesTestModel(name=self.test_input.initial)
        await model.asave()
        return model

    async def perform_action(self, piped):
        piped.name *= self.test_input.operand

    def expected_before(self):
        return self.test_input.initial

    def expected_after(self):
        return self.test_input.expected


@pytest.mark.asyncio
async def test_redis_str_combined_iadd_and_imul_with_pipeline_sanity():
    # Arrange
    model = PipelineAllTypesTestModel(name="ab")
    await model.asave()

    # Act
    async with model.apipeline() as m:
        m.name *= 2  # "abab"
        m.name += "_end"  # "abab_end"

        # Assert - changes not visible during pipeline
        loaded = await PipelineAllTypesTestModel.aget(model.key)
        assert loaded.name == "ab"

    # Assert - all changes applied after pipeline
    final = await PipelineAllTypesTestModel.aget(model.key)
    assert final.name == "abab_end"
