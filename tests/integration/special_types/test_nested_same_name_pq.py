import pytest
import pytest_asyncio

from tests.models.special_types import NestedSameNamePQModel


@pytest_asyncio.fixture
async def saved_nested_model():
    model = NestedSameNamePQModel()
    await model.asave()
    return model


@pytest.mark.asyncio
async def test_outer_and_inner_same_name_pq_have_distinct_special_keys(
    saved_nested_model,
):
    # Arrange
    model = saved_nested_model

    # Act
    outer_key = model.tasks.special_key
    inner_key = model.inner.tasks.special_key

    # Assert
    assert outer_key != inner_key


@pytest.mark.asyncio
async def test_push_to_outer_does_not_affect_inner(saved_nested_model):
    # Arrange
    model = saved_nested_model

    # Act
    await model.tasks.apush("outer_a", 1.0)
    await model.tasks.apush("outer_b", 2.0)

    # Assert
    assert await model.tasks.asize() == 2
    assert await model.inner.tasks.asize() == 0
    assert await model.inner.tasks.apop() is None


@pytest.mark.asyncio
async def test_push_to_inner_does_not_affect_outer(saved_nested_model):
    # Arrange
    model = saved_nested_model

    # Act
    await model.inner.tasks.apush("inner_a", 1.0)
    await model.inner.tasks.apush("inner_b", 2.0)

    # Assert
    assert await model.inner.tasks.asize() == 2
    assert await model.tasks.asize() == 0
    assert await model.tasks.apop() is None
