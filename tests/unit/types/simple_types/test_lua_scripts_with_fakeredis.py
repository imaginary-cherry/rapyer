import pytest

from tests.models.redis_types import PipelineAllTypesTestModel


@pytest.fixture
def setup_fake_redis(fake_redis_client):
    original_redis = PipelineAllTypesTestModel.Meta.redis
    PipelineAllTypesTestModel.Meta.redis = fake_redis_client
    yield
    PipelineAllTypesTestModel.Meta.redis = original_redis


@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [10, 3, 30],
        [5, 0, 0],
        [7, -2, -14],
    ],
)
@pytest.mark.asyncio
async def test_lua_num_mul_int_with_fakeredis_sanity(
    setup_fake_redis, initial_value, operand, expected
):
    # Arrange
    model = PipelineAllTypesTestModel(counter=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.counter *= operand

    # Assert
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.counter == expected


@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [17, 5, 3],
        [100, 7, 14],
        [25, 4, 6],
    ],
)
@pytest.mark.asyncio
async def test_lua_num_floordiv_int_with_fakeredis_sanity(
    setup_fake_redis, initial_value, operand, expected
):
    # Arrange
    model = PipelineAllTypesTestModel(counter=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.counter //= operand

    # Assert
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.counter == expected


@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [17, 5, 2],
        [23, 7, 2],
        [100, 9, 1],
    ],
)
@pytest.mark.asyncio
async def test_lua_num_mod_int_with_fakeredis_sanity(
    setup_fake_redis, initial_value, operand, expected
):
    # Arrange
    model = PipelineAllTypesTestModel(counter=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.counter %= operand

    # Assert
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.counter == expected


@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [2, 3, 8],
        [3, 2, 9],
        [5, 2, 25],
    ],
)
@pytest.mark.asyncio
async def test_lua_num_pow_int_with_fakeredis_sanity(
    setup_fake_redis, initial_value, operand, expected
):
    # Arrange
    model = PipelineAllTypesTestModel(counter=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.counter **= operand

    # Assert
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.counter == expected


@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [10.0, 2.5, 25.0],
        [3.0, 0, 0.0],
    ],
)
@pytest.mark.asyncio
async def test_lua_num_mul_float_with_fakeredis_sanity(
    setup_fake_redis, initial_value, operand, expected
):
    # Arrange
    model = PipelineAllTypesTestModel(amount=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.amount *= operand

    # Assert
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.amount == expected


@pytest.mark.parametrize(
    ["initial_value", "operand", "expected"],
    [
        [100.0, 5, 20.0],
        [10.0, 4, 2.5],
    ],
)
@pytest.mark.asyncio
async def test_lua_num_truediv_float_with_fakeredis_sanity(
    setup_fake_redis, initial_value, operand, expected
):
    # Arrange
    model = PipelineAllTypesTestModel(amount=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.amount /= operand

    # Assert
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.amount == expected


@pytest.mark.parametrize(
    ["initial_value", "suffix", "expected"],
    [
        ["hello", "_world", "hello_world"],
        ["", "test", "test"],
    ],
)
@pytest.mark.asyncio
async def test_lua_str_append_with_fakeredis_sanity(
    setup_fake_redis, initial_value, suffix, expected
):
    # Arrange
    model = PipelineAllTypesTestModel(name=initial_value)
    await model.asave()

    # Act
    async with model.apipeline() as redis_model:
        redis_model.name += suffix

    # Assert
    final_model = await PipelineAllTypesTestModel.aget(model.key)
    assert final_model.name == expected
