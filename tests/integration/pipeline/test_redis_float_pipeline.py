import pytest

from tests.models.redis_types import PipelineAllTypesTestModel


@pytest.mark.asyncio
async def test_redis_float_operations__all_operations_combined__check_atomicity_sanity():
    # Arrange
    model = PipelineAllTypesTestModel(amount=100.0)
    await model.asave()

    # Act
    async with model.apipeline() as m:
        m.amount += 50.0
        m.amount -= 25.0
        m.amount *= 2.0
        m.amount /= 5.0
        m.amount //= 3.0
        m.amount %= 10.0
        m.amount **= 2.0

        # Assert - changes not visible during pipeline
        loaded = await PipelineAllTypesTestModel.aget(model.key)
        assert loaded.amount == 100.0

    # Assert - all changes applied after pipeline
    final = await PipelineAllTypesTestModel.aget(model.key)
    assert final.amount == 36.0


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [100.0, 4.0, 25.0],
        [15.0, 2.0, 7.5],
        [10.0, 3.0, pytest.approx(3.3333333333333335)],
    ],
)
async def test_redis_float_itruediv_with_pipeline_sanity(
    initial_value: float, operand: float, expected: float
):
    # Arrange
    model = PipelineAllTypesTestModel(amount=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.amount /= operand

        # Assert - Change should not be applied yet
        loaded_model = await PipelineAllTypesTestModel.aget(model.key)
        assert loaded_model.amount == initial_value

    # Assert - Change should be applied after pipeline
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.amount == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [17.0, 5.0, 3.0],
        [100.5, 7.0, 14.0],
        [25.9, 4.0, 6.0],
    ],
)
async def test_redis_float_ifloordiv_with_pipeline_sanity(
    initial_value, operand, expected
):
    # Arrange
    model = PipelineAllTypesTestModel(amount=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.amount //= operand

        # Assert - Change should not be applied yet
        loaded_model = await PipelineAllTypesTestModel.aget(model.key)
        assert loaded_model.amount == initial_value

    # Assert - Change should be applied after pipeline
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.amount == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [17.5, 5.0, 2.5],
        [23.0, 7.0, 2.0],
        [100.3, 9.0, pytest.approx(1.3)],
    ],
)
async def test_redis_float_imod_with_pipeline_sanity(
    initial_value: float, operand, expected
):
    # Arrange
    model = PipelineAllTypesTestModel(amount=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.amount %= operand

        # Assert - Change should not be applied yet
        loaded_model = await PipelineAllTypesTestModel.aget(model.key)
        assert loaded_model.amount == initial_value

    # Assert - Change should be applied after pipeline
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.amount == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [2.0, 3.0, 8.0],
        [3.0, 2.0, 9.0],
        [4.0, 0.5, 2.0],
    ],
)
async def test_redis_float_ipow_with_pipeline_sanity(initial_value, operand, expected):
    # Arrange
    model = PipelineAllTypesTestModel(amount=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.amount **= operand

        # Assert - Change should not be applied yet
        loaded_model = await PipelineAllTypesTestModel.aget(model.key)
        assert loaded_model.amount == initial_value

    # Assert - Change should be applied after pipeline
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.amount == expected
