from datetime import datetime, timedelta

import pytest

from tests.models.redis_types import PipelineAllTypesTestModel
from tests.models.simple_types import DatetimeModel, DatetimeTimestampModel


@pytest.fixture
def setup_fake_redis(fake_redis_client):
    original_redis = PipelineAllTypesTestModel.Meta.redis
    original_is_fake = PipelineAllTypesTestModel.Meta.is_fake_redis
    PipelineAllTypesTestModel.Meta.redis = fake_redis_client
    PipelineAllTypesTestModel.Meta.is_fake_redis = True
    yield
    PipelineAllTypesTestModel.Meta.redis = original_redis
    PipelineAllTypesTestModel.Meta.is_fake_redis = original_is_fake


@pytest.fixture
def setup_fake_redis_datetime(fake_redis_client):
    original_redis = DatetimeModel.Meta.redis
    original_ts_redis = DatetimeTimestampModel.Meta.redis
    original_is_fake = DatetimeModel.Meta.is_fake_redis
    original_ts_is_fake = DatetimeTimestampModel.Meta.is_fake_redis
    DatetimeModel.Meta.redis = fake_redis_client
    DatetimeTimestampModel.Meta.redis = fake_redis_client
    DatetimeModel.Meta.is_fake_redis = True
    DatetimeTimestampModel.Meta.is_fake_redis = True
    yield
    DatetimeModel.Meta.redis = original_redis
    DatetimeTimestampModel.Meta.redis = original_ts_redis
    DatetimeModel.Meta.is_fake_redis = original_is_fake
    DatetimeTimestampModel.Meta.is_fake_redis = original_ts_is_fake


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


@pytest.mark.asyncio
async def test_lua_str_all_operations_with_fakeredis_sanity(setup_fake_redis):
    # Arrange
    model1 = PipelineAllTypesTestModel(name="ab")
    model2 = PipelineAllTypesTestModel(name="xy")
    await PipelineAllTypesTestModel.ainsert(model1, model2)

    # Act
    async with model1.apipeline():
        model1.name *= 2  # "abab"
        model2.name += "_end"  # "xy_end"

    # Assert
    final1, final2 = await PipelineAllTypesTestModel.afind(model1.key, model2.key)
    assert final1.name == "abab"
    assert final2.name == "xy_end"


@pytest.mark.asyncio
async def test_lua_float_all_operations_with_fakeredis_sanity(setup_fake_redis):
    # Arrange
    model1 = PipelineAllTypesTestModel(amount=100.0)
    model2 = PipelineAllTypesTestModel(amount=50.0)
    model3 = PipelineAllTypesTestModel(amount=17.0)
    model4 = PipelineAllTypesTestModel(amount=2.0)
    await PipelineAllTypesTestModel.ainsert(model1, model2, model3, model4)

    # Act
    async with model1.apipeline():
        model1.amount += 50.0  # 150.0
        model1.amount -= 25.0  # 125.0
        model2.amount *= 2.0  # 100.0
        model2.amount /= 4.0  # 25.0
        model3.amount //= 5.0  # 3.0
        model3.amount %= 2.0  # 1.0
        model4.amount **= 3.0  # 8.0

    # Assert
    final1, final2, final3, final4 = await PipelineAllTypesTestModel.afind(
        model1.key, model2.key, model3.key, model4.key
    )
    assert final1.amount == 125.0
    assert final2.amount == 25.0
    assert final3.amount == 1.0
    assert final4.amount == 8.0


@pytest.mark.asyncio
async def test_lua_datetime_all_operations_with_fakeredis_sanity(
    setup_fake_redis_datetime,
):
    # Arrange
    initial = datetime(2023, 1, 1, 12, 0, 0)
    model1 = DatetimeModel(created_at=initial, updated_at=initial)
    model2 = DatetimeModel(created_at=initial, updated_at=initial)
    await DatetimeModel.ainsert(model1, model2)

    # Act
    async with model1.apipeline():
        model1.created_at += timedelta(days=1)  # 2023-01-02 12:00:00
        model2.updated_at -= timedelta(hours=6)  # 2023-01-01 06:00:00

    # Assert
    final1, final2 = await DatetimeModel.afind(model1.key, model2.key)
    assert final1.created_at == datetime(2023, 1, 2, 12, 0, 0)
    assert final2.updated_at == datetime(2023, 1, 1, 6, 0, 0)


@pytest.mark.asyncio
async def test_lua_datetime_timestamp_all_operations_with_fakeredis_sanity(
    setup_fake_redis_datetime,
):
    # Arrange
    initial = datetime(2023, 1, 1, 12, 0, 0)
    model1 = DatetimeTimestampModel(created_at=initial, updated_at=initial)
    model2 = DatetimeTimestampModel(created_at=initial, updated_at=initial)
    await DatetimeTimestampModel.ainsert(model1, model2)

    # Act
    async with model1.apipeline():
        model1.created_at += timedelta(days=1)  # 2023-01-02 12:00:00
        model2.updated_at -= timedelta(hours=6)  # 2023-01-01 06:00:00

    # Assert
    final1, final2 = await DatetimeTimestampModel.afind(model1.key, model2.key)
    assert final1.created_at == datetime(2023, 1, 2, 12, 0, 0)
    assert final2.updated_at == datetime(2023, 1, 1, 6, 0, 0)
