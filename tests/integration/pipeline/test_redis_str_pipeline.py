import pytest

from tests.models.redis_types import PipelineAllTypesTestModel


@pytest.mark.asyncio
async def test_redis_str_operations__all_operations_combined__check_atomicity_sanity():
    # Arrange
    model = PipelineAllTypesTestModel(name="hello")
    await model.asave()

    # Act
    async with model.apipeline() as m:
        m.name += "_world"
        m.name += "_test"

        # Assert - changes not visible during pipeline
        loaded = await PipelineAllTypesTestModel.aget(model.key)
        assert loaded.name == "hello"

    # Assert - all changes applied after pipeline
    final = await PipelineAllTypesTestModel.aget(model.key)
    assert final.name == "hello_world_test"


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_value", "multiplier", "expected"],
    [["test", 0, ""]],
)
async def test_redis_str_imul_with_pipeline_sanity(initial_value, multiplier, expected):
    # Arrange
    model = PipelineAllTypesTestModel(name=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.name *= multiplier

        # Assert - Change should not be applied yet
        loaded_model = await PipelineAllTypesTestModel.aget(model.key)
        assert loaded_model.name == initial_value

    # Assert - Change should be applied after pipeline
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.name == expected


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
