import pytest

import rapyer
from tests.models.simple_types import StrModel


@pytest.mark.asyncio
async def test_rapyer_afind_one_returns_model_sanity():
    # Arrange
    model = StrModel(name="test_user", description="test description")
    await model.asave()

    # Act
    result = await rapyer.afind_one(model.key)

    # Assert
    assert result == model


@pytest.mark.asyncio
async def test_rapyer_afind_one_with_non_existent_key_returns_none_edge_case():
    # Arrange
    non_existent_key = "StrModel:non_existent_key_12345"

    # Act
    result = await rapyer.afind_one(non_existent_key)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_rapyer_afind_one_with_unknown_class_prefix_returns_none_edge_case():
    # Arrange
    unknown_class_key = "UnknownClass:some_key"

    # Act
    result = await rapyer.afind_one(unknown_class_key)

    # Assert
    assert result is None
