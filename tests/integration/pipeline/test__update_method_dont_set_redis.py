from datetime import datetime, timedelta

import pytest

import rapyer
from tests.models.collection_types import ComprehensiveTestModel
from tests.models.simple_types import (
    FloatModel,
    DatetimeModel,
    DatetimeTimestampModel,
)


# ===== RedisInt tests (ComprehensiveTestModel.counter) =====


@pytest.mark.asyncio
async def test_redis_int_iadd_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(counter=10)
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.counter = 50

    async with rapyer.apipeline():
        external_model.counter += 5

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == 15


@pytest.mark.asyncio
async def test_redis_int_isub_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(counter=10)
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.counter = 50

    async with rapyer.apipeline():
        external_model.counter -= 3

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == 7


@pytest.mark.asyncio
async def test_redis_int_imul_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(counter=10)
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.counter = 50

    async with rapyer.apipeline():
        external_model.counter *= 3

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == 30


@pytest.mark.asyncio
async def test_redis_int_ifloordiv_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(counter=10)
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.counter = 50

    async with rapyer.apipeline():
        external_model.counter //= 3

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == 3


@pytest.mark.asyncio
async def test_redis_int_imod_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(counter=10)
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.counter = 50

    async with rapyer.apipeline():
        external_model.counter %= 3

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == 1


@pytest.mark.asyncio
async def test_redis_int_ipow_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(counter=2)
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.counter = 50

    async with rapyer.apipeline():
        external_model.counter **= 3

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.counter == 8


# ===== RedisFloat tests (FloatModel.value) =====


@pytest.mark.asyncio
async def test_redis_float_iadd_with_pipeline_after_external_change():
    model = FloatModel(value=10.0)
    await model.asave()

    external_model = await FloatModel.aget(model.key)
    external_model.value = 50.0

    async with rapyer.apipeline():
        external_model.value += 5.5

    final_model = await FloatModel.aget(model.key)
    assert final_model.value == 15.5


@pytest.mark.asyncio
async def test_redis_float_isub_with_pipeline_after_external_change():
    model = FloatModel(value=10.0)
    await model.asave()

    external_model = await FloatModel.aget(model.key)
    external_model.value = 50.0

    async with rapyer.apipeline():
        external_model.value -= 3.5

    final_model = await FloatModel.aget(model.key)
    assert final_model.value == 6.5


@pytest.mark.asyncio
async def test_redis_float_imul_with_pipeline_after_external_change():
    model = FloatModel(value=10.0)
    await model.asave()

    external_model = await FloatModel.aget(model.key)
    external_model.value = 50.0

    async with rapyer.apipeline():
        external_model.value *= 3.0

    final_model = await FloatModel.aget(model.key)
    assert final_model.value == 30.0


@pytest.mark.asyncio
async def test_redis_float_itruediv_with_pipeline_after_external_change():
    model = FloatModel(value=10.0)
    await model.asave()

    external_model = await FloatModel.aget(model.key)
    external_model.value = 50.0

    async with rapyer.apipeline():
        external_model.value /= 4.0

    final_model = await FloatModel.aget(model.key)
    assert final_model.value == 2.5


@pytest.mark.asyncio
async def test_redis_float_ifloordiv_with_pipeline_after_external_change():
    model = FloatModel(value=10.0)
    await model.asave()

    external_model = await FloatModel.aget(model.key)
    external_model.value = 50.0

    async with rapyer.apipeline():
        external_model.value //= 3.0

    final_model = await FloatModel.aget(model.key)
    assert final_model.value == 3.0


@pytest.mark.asyncio
async def test_redis_float_imod_with_pipeline_after_external_change():
    model = FloatModel(value=10.0)
    await model.asave()

    external_model = await FloatModel.aget(model.key)
    external_model.value = 50.0

    async with rapyer.apipeline():
        external_model.value %= 3.0

    final_model = await FloatModel.aget(model.key)
    assert final_model.value == 1.0


@pytest.mark.asyncio
async def test_redis_float_ipow_with_pipeline_after_external_change():
    model = FloatModel(value=2.0)
    await model.asave()

    external_model = await FloatModel.aget(model.key)
    external_model.value = 50.0

    async with rapyer.apipeline():
        external_model.value **= 3.0

    final_model = await FloatModel.aget(model.key)
    assert final_model.value == 8.0


# ===== RedisStr tests (ComprehensiveTestModel.name) =====


@pytest.mark.asyncio
async def test_redis_str_iadd_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(name="hello")
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.name = "changed"

    async with rapyer.apipeline():
        external_model.name += "_world"

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.name == "hello_world"


@pytest.mark.asyncio
async def test_redis_str_imul_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(name="ab")
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.name = "changed"

    async with rapyer.apipeline():
        external_model.name *= 3

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.name == "ababab"


# ===== RedisDatetime tests (DatetimeModel.created_at) =====


@pytest.mark.asyncio
async def test_redis_datetime_iadd_with_pipeline_after_external_change():
    model = DatetimeModel(created_at=datetime(2023, 1, 1, 12, 0, 0))
    await model.asave()

    external_model = await DatetimeModel.aget(model.key)
    external_model.created_at = datetime(2025, 6, 15)

    async with rapyer.apipeline():
        external_model.created_at += timedelta(days=1)

    final_model = await DatetimeModel.aget(model.key)
    assert final_model.created_at == datetime(2023, 1, 2, 12, 0, 0)


@pytest.mark.asyncio
async def test_redis_datetime_isub_with_pipeline_after_external_change():
    model = DatetimeModel(created_at=datetime(2023, 1, 10, 12, 0, 0))
    await model.asave()

    external_model = await DatetimeModel.aget(model.key)
    external_model.created_at = datetime(2025, 6, 15)

    async with rapyer.apipeline():
        external_model.created_at -= timedelta(days=1)

    final_model = await DatetimeModel.aget(model.key)
    assert final_model.created_at == datetime(2023, 1, 9, 12, 0, 0)


# ===== RedisDatetimeTimestamp tests (DatetimeTimestampModel.created_at) =====


@pytest.mark.asyncio
async def test_redis_datetime_timestamp_iadd_with_pipeline_after_external_change():
    model = DatetimeTimestampModel(created_at=datetime(2023, 1, 1, 12, 0, 0))
    await model.asave()

    external_model = await DatetimeTimestampModel.aget(model.key)
    external_model.created_at = datetime(2025, 6, 15)

    async with rapyer.apipeline():
        external_model.created_at += timedelta(hours=6)

    final_model = await DatetimeTimestampModel.aget(model.key)
    assert final_model.created_at == datetime(2023, 1, 1, 18, 0, 0)


@pytest.mark.asyncio
async def test_redis_datetime_timestamp_isub_with_pipeline_after_external_change():
    model = DatetimeTimestampModel(created_at=datetime(2023, 1, 10, 12, 0, 0))
    await model.asave()

    external_model = await DatetimeTimestampModel.aget(model.key)
    external_model.created_at = datetime(2025, 6, 15)

    async with rapyer.apipeline():
        external_model.created_at -= timedelta(hours=6)

    final_model = await DatetimeTimestampModel.aget(model.key)
    assert final_model.created_at == datetime(2023, 1, 10, 6, 0, 0)


# ===== RedisList tests (ComprehensiveTestModel.tags) =====


@pytest.mark.asyncio
async def test_redis_list_append_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(tags=["a", "b"])
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.tags = ["x", "y", "z"]

    async with rapyer.apipeline():
        external_model.tags.append("c")

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_redis_list_extend_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(tags=["a", "b"])
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.tags = ["x", "y", "z"]

    async with rapyer.apipeline():
        external_model.tags += ["c", "d"]

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["a", "b", "c", "d"]


@pytest.mark.asyncio
async def test_redis_list_insert_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(tags=["a", "b"])
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.tags = ["x", "y", "z"]

    async with rapyer.apipeline():
        external_model.tags.insert(1, "c")

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["a", "c", "b"]


# ===== RedisDict tests (ComprehensiveTestModel.metadata) =====


@pytest.mark.asyncio
async def test_redis_dict_update_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(metadata={"key1": "val1"})
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.metadata = {"changed": "data"}

    async with rapyer.apipeline():
        external_model.metadata.update({"key2": "val2"})

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.metadata == {"key1": "val1", "key2": "val2"}


@pytest.mark.asyncio
async def test_redis_dict_setitem_with_pipeline_after_external_change():
    model = ComprehensiveTestModel(metadata={"key1": "val1"})
    await model.asave()

    external_model = await ComprehensiveTestModel.aget(model.key)
    external_model.metadata = {"changed": "data"}

    async with rapyer.apipeline():
        external_model.metadata["key2"] = "val2"

    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.metadata == {"key1": "val1", "key2": "val2"}
