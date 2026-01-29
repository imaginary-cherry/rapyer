import base64
import pickle

import pytest

from tests.models.unknown_types import (
    StrStatus,
    IntPriority,
    ModelWithStrEnumDefault,
    ModelWithIntEnumDefault,
    ModelWithStrEnumInList,
    ModelWithStrEnumInDict,
)


@pytest.mark.asyncio
async def test_str_enum_field_save_and_load_sanity(real_redis_client):
    # Arrange
    model = ModelWithStrEnumDefault(status=StrStatus.PENDING, name="test_model")

    # Act
    await model.asave()
    loaded = await ModelWithStrEnumDefault.aget(model.key)

    # Assert
    assert loaded.status == StrStatus.PENDING
    assert loaded.name == "test_model"


@pytest.mark.asyncio
async def test_int_enum_field_save_and_load_sanity(real_redis_client):
    # Arrange
    model = ModelWithIntEnumDefault(priority=IntPriority.MEDIUM, name="test_model")

    # Act
    await model.asave()
    loaded = await ModelWithIntEnumDefault.aget(model.key)

    # Assert
    assert loaded.priority == IntPriority.MEDIUM
    assert loaded.name == "test_model"


@pytest.mark.asyncio
async def test_str_enum_in_list_save_and_load_sanity(real_redis_client):
    # Arrange
    model = ModelWithStrEnumInList(
        statuses=[StrStatus.ACTIVE, StrStatus.INACTIVE, StrStatus.PENDING],
        name="list_model",
    )

    # Act
    await model.asave()
    loaded = await ModelWithStrEnumInList.aget(model.key)

    # Assert
    assert loaded.statuses == [StrStatus.ACTIVE, StrStatus.INACTIVE, StrStatus.PENDING]
    assert loaded.name == "list_model"


@pytest.mark.asyncio
async def test_str_enum_in_dict_save_and_load_sanity(real_redis_client):
    # Arrange
    model = ModelWithStrEnumInDict(
        status_map={"a": StrStatus.ACTIVE, "b": StrStatus.INACTIVE},
        name="dict_model",
    )

    # Act
    await model.asave()
    loaded = await ModelWithStrEnumInDict.aget(model.key)

    # Assert
    assert loaded.status_map == {"a": StrStatus.ACTIVE, "b": StrStatus.INACTIVE}
    assert loaded.name == "dict_model"
