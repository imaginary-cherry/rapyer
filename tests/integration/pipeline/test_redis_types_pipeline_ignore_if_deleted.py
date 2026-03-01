from datetime import datetime

import pytest

from tests.models.functionality_types import AllTypesModel, MyTestEnum


@pytest.mark.parametrize(
    ["field_name", "test_value"],
    [
        ["str_field", "test_string"],
        ["int_field", 42],
        ["datetime_field", datetime(2023, 1, 1, 12, 0, 0)],
    ],
)
@pytest.mark.asyncio
async def test_redis_types_pipeline_ignore_redis_error_true__model_not_saved_pipeline_actions_model_not_created_sanity(
    real_redis_client, field_name, test_value
):
    # Arrange
    model = AllTypesModel()

    # Act
    async with model.apipeline(ignore_redis_error=True) as redis_model:
        field = getattr(redis_model, field_name)
        setattr(redis_model, field_name, test_value)
        await field.asave()

        # Assert - model should not be created yet
        model_exists = await real_redis_client.exists(model.key)
        assert model_exists == 0

    # Assert - model should still not be created after pipeline
    model_exists = await real_redis_client.exists(model.key)
    assert model_exists == 0


@pytest.mark.parametrize(
    ["field_name", "test_value"],
    [
        ["str_field", "test_string"],
        ["int_field", 42],
        ["bool_field", True],
        ["datetime_field", datetime(2023, 1, 1, 12, 0, 0)],
        ["bytes_field", b"test_bytes"],
        ["any_field", {"nested": "object"}],
        ["enum_field", MyTestEnum.OPTION_B],
    ],
)
@pytest.mark.asyncio
async def test_redis_types_pipeline_ignore_redis_error_false__model_not_saved_error_raised_edge_case(
    field_name, test_value
):
    # Arrange
    model = AllTypesModel()

    # Act & Assert
    with pytest.raises(Exception):
        async with model.apipeline(ignore_redis_error=False) as redis_model:
            field = getattr(redis_model, field_name)
            setattr(redis_model, field_name, test_value)
            await field.asave()


@pytest.mark.asyncio
async def test_redis_list_pipeline_ignore_redis_error_true__model_not_saved_pipeline_actions_model_not_created_sanity(
    real_redis_client,
):
    # Arrange
    model = AllTypesModel()

    # Act
    async with model.apipeline(ignore_redis_error=True) as redis_model:
        await redis_model.list_field.aappend("item1")
        await redis_model.list_field.aextend(["item2", "item3"])

        # Assert - model should not be created yet
        model_exists = await real_redis_client.exists(model.key)
        assert model_exists == 0

    # Assert - model should still not be created after pipeline
    model_exists = await real_redis_client.exists(model.key)
    assert model_exists == 0


@pytest.mark.asyncio
async def test_redis_list_pipeline_ignore_redis_error_false__model_not_saved_error_raised_edge_case():
    # Arrange
    model = AllTypesModel()

    # Act & Assert
    with pytest.raises(Exception):
        async with model.apipeline(ignore_redis_error=False) as redis_model:
            redis_model.list_field.append("item1")


@pytest.mark.asyncio
async def test_redis_dict_pipeline_ignore_redis_error_true__model_not_saved_pipeline_actions_model_not_created_sanity(
    real_redis_client,
):
    # Arrange
    model = AllTypesModel()

    # Act
    async with model.apipeline(ignore_redis_error=True) as redis_model:
        redis_model.dict_field["key1"] = "value1"
        redis_model.dict_field.update(key2="value2", key3="value3")

        # Assert - model should not be created yet
        model_exists = await real_redis_client.exists(model.key)
        assert model_exists == 0

    # Assert - model should still not be created after pipeline
    model_exists = await real_redis_client.exists(model.key)
    assert model_exists == 0
