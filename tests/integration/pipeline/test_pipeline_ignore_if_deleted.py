import pytest

from rapyer.errors import KeyNotFound
from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
async def test_apipeline_ignore_if_deleted_true__model_not_saved_returns_created_model_sanity():
    # Arrange
    model = ComprehensiveTestModel(name="test", counter=42)

    # Act
    async with model.apipeline(ignore_if_deleted=True) as redis_model:
        pass

    # Assert
    assert redis_model is model


@pytest.mark.asyncio
async def test_apipeline_ignore_if_deleted_false__model_not_saved_raises_key_not_found_edge_case():
    # Arrange
    model = ComprehensiveTestModel(name="test", counter=42)

    # Act & Assert
    with pytest.raises(KeyNotFound):
        async with model.apipeline(ignore_if_deleted=False) as redis_model:
            pass
