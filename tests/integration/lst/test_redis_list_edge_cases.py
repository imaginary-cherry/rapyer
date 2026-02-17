import pytest
from rapyer.types.lst import RedisList
from redis import ResponseError
from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
async def test_redis_list_apop_returns_none_for_empty_list_edge_case():
    # Arrange
    model = ComprehensiveTestModel(tags=[])
    await model.asave()

    # Act
    result = await model.tags.apop()

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_redis_list_apop_returns_none_after_emptying_list_edge_case():
    # Arrange
    model = ComprehensiveTestModel(tags=["single_item"])
    await model.asave()

    # Pop the only item
    first_pop = await model.tags.apop()
    assert first_pop == "single_item"

    # Act - Pop from now empty list
    second_pop = await model.tags.apop()

    # Assert
    assert second_pop is None


@pytest.mark.asyncio
async def test_redis_list_apop_on_unsaved_model_raises_error_edge_case():
    # Arrange - model NOT saved to Redis
    model = ComprehensiveTestModel(tags=["item"])

    # Act & Assert - apop on non-existent Redis key should raise RuntimeError
    with pytest.raises(ResponseError):
        await model.tags.apop()


def test_redis_list_clone_returns_native_list_sanity():
    # Arrange
    model = ComprehensiveTestModel(tags=["item1", "item2", "item3"])

    # Act
    cloned = model.tags.clone()

    # Assert
    assert cloned == ["item1", "item2", "item3"]
    assert isinstance(cloned, list)
    assert not isinstance(cloned, RedisList)
