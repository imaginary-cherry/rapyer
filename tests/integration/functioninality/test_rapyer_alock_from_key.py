import asyncio
from datetime import datetime
from unittest.mock import Mock

import pytest

import rapyer
from tests.models.functionality_types import RichModel


@pytest.mark.asyncio
async def test_alock_from_key_with_existing_key_and_save_at_end_true_sanity():
    # Arrange
    model = RichModel(name="test_lock", age=25, tags=["initial"], date1="2023-01-01")
    await model.asave()

    # Act
    async with rapyer.alock_from_key(model.key, save_at_end=True) as locked_model:
        locked_model.name = "modified_name"
        locked_model.age = 30
        locked_model.tags.append("new_tag")
        locked_model.date1 = "2023-12-31"

    # Assert
    retrieved_model = await RichModel.aget(model.key)
    assert retrieved_model.name == "modified_name"
    assert retrieved_model.age == 30
    assert retrieved_model.tags == ["initial", "new_tag"]
    assert retrieved_model.date1 == "2023-12-31"


@pytest.mark.asyncio
async def test_alock_from_key_with_nonexistent_key_edge_case(redis_client):
    # Arrange
    nonexistent_key = "nonexistent:model:key:12345"

    # Act & Assert
    async with rapyer.alock_from_key(nonexistent_key, save_at_end=True) as locked_model:
        assert locked_model is None
    keys = await redis_client.keys()
    assert nonexistent_key not in keys


@pytest.mark.asyncio
async def test_alock_from_key_with_concurrent_access_sanity():
    # Arrange
    model = RichModel(name="concurrent_test", date1="initial_date")
    await model.asave()

    enter_mock = Mock()
    exit_mock = Mock()

    async def lock_and_modify(model_key: str, delay_seconds: int):
        async with rapyer.alock_from_key(model_key, save_at_end=True) as locked_model:
            current_time = datetime.now().isoformat()
            enter_mock(current_time, locked_model.model_dump())

            await asyncio.sleep(delay_seconds)

            exit_date = datetime.now().isoformat()
            locked_model.date1 = exit_date
            exit_mock(exit_date)

    # Act
    await asyncio.gather(lock_and_modify(model.key, 3), lock_and_modify(model.key, 3))

    # Assert
    assert enter_mock.call_count == 2
    assert exit_mock.call_count == 2

    enter_calls = enter_mock.call_args_list
    exit_calls = exit_mock.call_args_list

    second_enter_time = datetime.fromisoformat(enter_calls[1][0][0])
    first_exit_time = datetime.fromisoformat(exit_calls[0][0][0])
    second_model_dump = enter_calls[1][0][1]
    second_model_dump = RichModel.model_validate(second_model_dump)

    assert second_enter_time > first_exit_time
    assert second_model_dump.date1 != "initial_date"


@pytest.mark.asyncio
async def test_alock_from_key_with_save_at_end_false_sanity():
    # Arrange
    model = RichModel(name="no_save_test", age=25, tags=["original"])
    await model.asave()

    # Act
    async with rapyer.alock_from_key(model.key, save_at_end=False) as locked_model:
        locked_model.name = "modified"
        locked_model.age = 30
        locked_model.tags.append("new")

    # Assert
    retrieved_model = await RichModel.aget(model.key)
    assert retrieved_model.name == "no_save_test"
    assert retrieved_model.age == 25
    assert retrieved_model.tags == ["original"]
