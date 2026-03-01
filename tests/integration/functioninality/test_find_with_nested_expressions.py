from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from tests.models.index_types import ChildWithParentModel, ParentWithIndexModel


@pytest_asyncio.fixture
async def create_nested_indices(redis_client):
    await ChildWithParentModel.acreate_index()
    yield
    await ChildWithParentModel.adelete_index()


@pytest.fixture
def nested_test_models():
    base_date = datetime(2024, 1, 1)
    return [
        ChildWithParentModel(
            name="Alice",
            dad=ParentWithIndexModel(
                age=45,
                occupation="Engineer",
                retirement_date=base_date + timedelta(days=365 * 10),
            ),
            birth_date=base_date,
        ),
        ChildWithParentModel(
            name="Bob",
            dad=ParentWithIndexModel(
                age=55,
                occupation="Doctor",
                retirement_date=base_date + timedelta(days=365 * 5),
            ),
            birth_date=base_date - timedelta(days=365 * 5),
        ),
        ChildWithParentModel(
            name="Charlie",
            dad=ParentWithIndexModel(
                age=50,
                occupation="Engineer",
                retirement_date=base_date + timedelta(days=365 * 7),
            ),
            birth_date=base_date - timedelta(days=365 * 2),
        ),
    ]


@pytest_asyncio.fixture
async def inserted_nested_models(nested_test_models):
    await ChildWithParentModel.ainsert(*nested_test_models)
    return nested_test_models


@pytest.mark.asyncio
async def test_afind_with_nested_numeric_expression_sanity(
    create_nested_indices, inserted_nested_models
):
    # Arrange
    ChildWithParentModel.init_class()

    # Act
    found_models = await ChildWithParentModel.afind(ChildWithParentModel.dad.age < 50)

    # Assert
    assert len(found_models) == 1
    assert found_models[0].name == "Alice"


@pytest.mark.asyncio
async def test_afind_with_nested_string_expression_sanity(
    create_nested_indices, inserted_nested_models
):
    # Arrange
    ChildWithParentModel.init_class()

    # Act
    found_models = await ChildWithParentModel.afind(
        ChildWithParentModel.dad.occupation == "Engineer"
    )

    # Assert
    assert len(found_models) == 2
    found_names = {m.name for m in found_models}
    assert "Alice" in found_names
    assert "Charlie" in found_names


@pytest.mark.asyncio
async def test_afind_with_nested_and_direct_field_combined_sanity(
    create_nested_indices, inserted_nested_models
):
    # Arrange
    ChildWithParentModel.init_class()

    # Act
    expression = (ChildWithParentModel.dad.age > 40) & (
        ChildWithParentModel.name == "Bob"
    )
    found_models = await ChildWithParentModel.afind(expression)

    # Assert
    assert len(found_models) == 1
    assert found_models[0].name == "Bob"


@pytest.mark.asyncio
async def test_afind_with_nested_datetime_expression_sanity(
    create_nested_indices, inserted_nested_models
):
    # Arrange
    ChildWithParentModel.init_class()
    cutoff_date = datetime(2024, 1, 1) + timedelta(days=365 * 6)

    # Act
    found_models = await ChildWithParentModel.afind(
        ChildWithParentModel.dad.retirement_date < cutoff_date
    )

    # Assert
    assert len(found_models) == 1
    assert found_models[0].name == "Bob"


@pytest.mark.asyncio
async def test_afind_with_nested_or_expression_sanity(
    create_nested_indices, inserted_nested_models
):
    # Arrange
    ChildWithParentModel.init_class()

    # Act
    expression = (ChildWithParentModel.dad.age < 46) | (
        ChildWithParentModel.dad.occupation == "Doctor"
    )
    found_models = await ChildWithParentModel.afind(expression)

    # Assert
    assert len(found_models) == 2
    found_names = {m.name for m in found_models}
    assert "Alice" in found_names
    assert "Bob" in found_names


@pytest.mark.asyncio
async def test_afind_with_nested_not_expression_sanity(
    create_nested_indices, inserted_nested_models
):
    # Arrange
    ChildWithParentModel.init_class()

    # Act
    expression = ~(ChildWithParentModel.dad.occupation == "Engineer")
    found_models = await ChildWithParentModel.afind(expression)

    # Assert
    assert len(found_models) == 1
    assert found_models[0].name == "Bob"


@pytest.mark.asyncio
async def test_afind_returns_empty_when_no_nested_match_edge_case(
    create_nested_indices, inserted_nested_models
):
    # Arrange
    ChildWithParentModel.init_class()

    # Act
    found_models = await ChildWithParentModel.afind(ChildWithParentModel.dad.age > 100)

    # Assert
    assert found_models == []
