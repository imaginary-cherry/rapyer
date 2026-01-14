import base64
import pickle

import pytest
import pytest_asyncio

from tests.models.unknown_types import (
    StrStatus,
    IntPriority,
    ModelWithStrEnumDefault,
    ModelWithIntEnumDefault,
    ModelWithStrEnumInList,
    ModelWithStrEnumInDict,
)


@pytest_asyncio.fixture
async def redis_client_fixture(redis_client):
    ModelWithStrEnumDefault.Meta.redis = redis_client
    ModelWithIntEnumDefault.Meta.redis = redis_client
    ModelWithStrEnumInList.Meta.redis = redis_client
    ModelWithStrEnumInDict.Meta.redis = redis_client
    yield redis_client
    await redis_client.aclose()


@pytest.mark.asyncio
async def test_str_enum_field_save_and_load_sanity(redis_client_fixture):
    # Arrange
    model = ModelWithStrEnumDefault(status=StrStatus.PENDING, name="test_model")

    # Act
    await model.asave()
    loaded = await ModelWithStrEnumDefault.aget(model.key)

    # Assert
    assert loaded.status == StrStatus.PENDING
    assert loaded.name == "test_model"


@pytest.mark.asyncio
async def test_int_enum_field_save_and_load_sanity(redis_client_fixture):
    # Arrange
    model = ModelWithIntEnumDefault(priority=IntPriority.MEDIUM, name="test_model")

    # Act
    await model.asave()
    loaded = await ModelWithIntEnumDefault.aget(model.key)

    # Assert
    assert loaded.priority == IntPriority.MEDIUM
    assert loaded.name == "test_model"


@pytest.mark.asyncio
async def test_str_enum_in_list_save_and_load_sanity(redis_client_fixture):
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
async def test_str_enum_in_dict_save_and_load_sanity(redis_client_fixture):
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


@pytest.mark.asyncio
async def test_str_enum_backward_compat_with_pickled_data_sanity(redis_client_fixture):
    # Arrange
    model = ModelWithStrEnumDefault(status=StrStatus.ACTIVE, name="backward_test")
    pickled_status = base64.b64encode(pickle.dumps(StrStatus.PENDING)).decode("utf-8")
    old_format_data = {"status": pickled_status, "name": "backward_test"}
    await redis_client_fixture.json().set(model.key, "$", old_format_data)

    # Act
    loaded = await ModelWithStrEnumDefault.aget(model.key)

    # Assert
    assert loaded.status == StrStatus.PENDING
    assert loaded.name == "backward_test"


@pytest.mark.asyncio
async def test_int_enum_backward_compat_with_pickled_data_sanity(redis_client_fixture):
    # Arrange
    model = ModelWithIntEnumDefault(priority=IntPriority.LOW, name="backward_test")
    pickled_priority = base64.b64encode(pickle.dumps(IntPriority.HIGH)).decode("utf-8")
    old_format_data = {"priority": pickled_priority, "name": "backward_test"}
    await redis_client_fixture.json().set(model.key, "$", old_format_data)

    # Act
    loaded = await ModelWithIntEnumDefault.aget(model.key)

    # Assert
    assert loaded.priority == IntPriority.HIGH
    assert loaded.name == "backward_test"
