import pytest

from tests.models.index_types import IndexTestModel


@pytest.mark.asyncio
async def test_afind_one_with_expression_returns_single_model(
    create_index, inserted_test_models
):
    # Arrange
    IndexTestModel.init_class()

    # Act
    result = await IndexTestModel.afind_one(IndexTestModel.age >= 30)

    # Assert
    assert result is not None
    assert result.age >= 30


@pytest.mark.asyncio
async def test_afind_one_with_no_match_returns_none(create_index, inserted_test_models):
    # Arrange
    IndexTestModel.init_class()

    # Act
    result = await IndexTestModel.afind_one(IndexTestModel.age > 100)

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_afind_one_with_key_returns_model(inserted_test_models):
    # Arrange
    model = inserted_test_models[0]

    # Act
    result = await IndexTestModel.afind_one(model.key)

    # Assert
    assert result is not None
    assert result == model


@pytest.mark.asyncio
async def test_afind_one_without_args_returns_single_model(inserted_test_models):
    # Act
    result = await IndexTestModel.afind_one()

    # Assert
    assert result is not None
    assert isinstance(result, IndexTestModel)
