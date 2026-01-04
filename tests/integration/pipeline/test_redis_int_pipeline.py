import pytest

from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [20, 5, 15],
        [100, 30, 70],
        [50, 50, 0],
    ],
)
async def test_redis_int_isub_with_pipeline_sanity(initial_value, operand, expected):
    # Arrange
    model = ComprehensiveTestModel(counter=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.counter -= operand

        # Assert - Change should not be applied yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.counter == initial_value

    # Assert - Change should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [5, 4, 20],
        [10, 3, 30],
        [7, 0, 0],
    ],
)
async def test_redis_int_imul_with_pipeline_sanity(initial_value, operand, expected):
    # Arrange
    model = ComprehensiveTestModel(counter=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.counter *= operand

        # Assert - Change should not be applied yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.counter == initial_value

    # Assert - Change should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [17, 5, 3],
        [100, 7, 14],
        [25, 4, 6],
    ],
)
async def test_redis_int_ifloordiv_with_pipeline_sanity(initial_value, operand, expected):
    # Arrange
    model = ComprehensiveTestModel(counter=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.counter //= operand

        # Assert - Change should not be applied yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.counter == initial_value

    # Assert - Change should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [17, 5, 2],
        [23, 7, 2],
        [100, 9, 1],
    ],
)
async def test_redis_int_imod_with_pipeline_sanity(initial_value, operand, expected):
    # Arrange
    model = ComprehensiveTestModel(counter=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.counter %= operand

        # Assert - Change should not be applied yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.counter == initial_value

    # Assert - Change should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [2, 3, 8],
        [3, 2, 9],
        [5, 2, 25],
    ],
)
async def test_redis_int_ipow_with_pipeline_sanity(initial_value, operand, expected):
    # Arrange
    model = ComprehensiveTestModel(counter=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.counter **= operand

        # Assert - Change should not be applied yet
        loaded_model = await ComprehensiveTestModel.aget(model.key)
        assert loaded_model.counter == initial_value

    # Assert - Change should be applied after pipeline
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == expected
