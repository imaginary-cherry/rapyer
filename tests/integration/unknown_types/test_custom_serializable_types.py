import pytest

from tests.models.unknown_types import (
    ComplexCustomType,
    CustomSerializableType,
    ModelWithCustomTypes,
    NestedPydanticModel,
)


@pytest.mark.asyncio
async def test_custom_serializable_types__save_and_get__check_equality_sanity():
    # Arrange
    original_model = ModelWithCustomTypes(
        simple_custom=CustomSerializableType(
            value="test_value", metadata={"key": "value", "number": 42}
        ),
        complex_custom=ComplexCustomType(
            name="complex_test",
            items=["item1", "item2", "item3"],
            config={"timeout": 30, "retries": 3},
        ),
        pydantic_nested=NestedPydanticModel(title="Test Title", count=100, active=True),
    )

    # Act
    await original_model.asave()
    retrieved_model = await ModelWithCustomTypes.aget(original_model.key)

    # Assert
    assert original_model == retrieved_model


@pytest.mark.asyncio
async def test_custom_serializable_types__model_reload__check_equality_sanity():
    # Arrange
    original_model = ModelWithCustomTypes(
        simple_custom=CustomSerializableType(
            value="reload_test", metadata={"env": "test", "version": 1}
        ),
        complex_custom=ComplexCustomType(
            name="reload_complex", items=["a", "b"], config={"max_size": 1000}
        ),
        pydantic_nested=NestedPydanticModel(
            title="Reload Test", count=50, active=False
        ),
    )
    await original_model.asave()

    # Act - get a fresh model from Redis
    reloaded_model = await ModelWithCustomTypes.aget(original_model.key)

    # Assert - values should be preserved
    assert reloaded_model == original_model
