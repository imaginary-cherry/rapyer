import pytest

from tests.models.index_types import IndexTestModel


@pytest.mark.asyncio
async def test_afind_with_max_results_limits_expression_results(
    create_index, inserted_test_models
):
    # Arrange
    IndexTestModel.init_class()

    # Act
    results = await IndexTestModel.afind(IndexTestModel.age >= 30, max_results=2)

    # Assert
    assert len(results) == 2
    assert all(m.age >= 30 for m in results)


@pytest.mark.asyncio
async def test_afind_with_max_results_limits_all_results(inserted_test_models):
    # Act
    results = await IndexTestModel.afind(max_results=2)

    # Assert
    assert len(results) == 2


@pytest.mark.asyncio
async def test_afind_with_max_results_limits_key_results(inserted_test_models):
    # Arrange
    keys = [m.key for m in inserted_test_models[:3]]

    # Act
    results = await IndexTestModel.afind(*keys, max_results=2)

    # Assert
    assert len(results) == 2
