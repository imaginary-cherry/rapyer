from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from rapyer.errors import BadFilterError
from tests.models.index_types import (
    IndexTestModel,
    BaseIndexModel,
    UserIndexModel,
    ProductIndexModel,
)


@pytest_asyncio.fixture
async def create_indices(redis_client):
    # Create index for IntModel
    await IndexTestModel.acreate_index()
    await BaseIndexModel.acreate_index()

    yield

    await IndexTestModel.adelete_index()
    await BaseIndexModel.adelete_index()


@pytest.mark.asyncio
async def test_afind_with_single_expression_sanity(
    create_indices, inserted_test_models
):
    # Arrange
    models = inserted_test_models

    # Act
    IndexTestModel.init_class()
    found_models = await IndexTestModel.afind(IndexTestModel.age > 30)

    # Assert
    assert len(found_models) == 2
    for model in models:
        if model.age > 30:
            assert model in found_models


@pytest.mark.asyncio
async def test_afind_with_multiple_expressions_sanity(
    create_indices, inserted_test_models
):
    # Arrange
    models = inserted_test_models

    # Act
    IndexTestModel.init_class()
    found_models = await IndexTestModel.afind(
        IndexTestModel.age >= 30, IndexTestModel.name == "Charlie"
    )

    # Assert
    assert len(found_models) == 1
    for model in models:
        if model.age >= 30 and model.name == "Charlie":
            assert model in found_models


@pytest.mark.asyncio
async def test_afind_with_combined_expressions_sanity(
    create_indices, inserted_test_models
):
    # Arrange
    models = inserted_test_models

    # Act
    IndexTestModel.init_class()
    expression = (IndexTestModel.age > 25) & (IndexTestModel.age < 40)
    found_models = await IndexTestModel.afind(expression)

    # Assert
    assert len(found_models) == 2
    for model in models:
        if model.age > 25 and model.age < 40:
            assert model in found_models


@pytest.mark.asyncio
async def test_afind_with_or_expression_sanity(create_indices, inserted_test_models):
    # Arrange
    models = inserted_test_models

    # Act
    IndexTestModel.init_class()
    expression = (IndexTestModel.age <= 25) | (IndexTestModel.age >= 40)
    found_models = await IndexTestModel.afind(expression)

    # Assert
    assert len(found_models) == 2
    for model in models:
        if model.age <= 25 or model.age >= 40:
            assert model in found_models


@pytest.fixture
def three_test_models():
    return [
        IndexTestModel(name="Alice", age=25, description="Engineer"),
        IndexTestModel(name="Bob", age=30, description="Manager"),
        IndexTestModel(name="Charlie", age=35, description="Designer"),
    ]


@pytest_asyncio.fixture
async def inserted_three_test_models(three_test_models):
    await IndexTestModel.ainsert(*three_test_models)
    return three_test_models


@pytest.mark.asyncio
async def test_afind_without_expressions_returns_all_sanity(inserted_three_test_models):
    # Arrange
    models = inserted_three_test_models

    # Act
    found_models = await IndexTestModel.afind()

    # Assert
    assert len(found_models) == 3
    for model in models:
        assert model in found_models


@pytest.mark.asyncio
async def test_afind_with_string_field_expression_sanity(
    create_indices, inserted_test_models
):
    # Arrange
    models = inserted_test_models

    # Act
    IndexTestModel.init_class()
    found_models = await IndexTestModel.afind(IndexTestModel.name == "Alice")

    # Assert
    assert len(found_models) == 1
    for model in models:
        if model.name == "Alice":
            assert model in found_models


@pytest.mark.asyncio
async def test_afind_with_not_expression_sanity(
    create_indices, inserted_three_test_models
):
    # Arrange
    models = inserted_three_test_models

    # Act
    IndexTestModel.init_class()
    expression = ~(IndexTestModel.age == 30)
    found_models = await IndexTestModel.afind(expression)

    # Assert
    assert len(found_models) == 2
    for model in models:
        if model.age != 30:
            assert model in found_models


# NOTE: Testing float type filtering (ProductIndexModel.price is float)
@pytest.mark.asyncio
async def test_afind_with_float_filtering_sanity(redis_client):
    # Arrange
    await ProductIndexModel.acreate_index()

    base_date = datetime(2024, 1, 1)
    product1 = ProductIndexModel(
        id="prod1", created_at=base_date, name="Laptop", price=1500.99
    )
    product2 = ProductIndexModel(
        id="prod2", created_at=base_date, name="Phone", price=899.50
    )
    product3 = ProductIndexModel(
        id="prod3", created_at=base_date, name="Tablet", price=599.99
    )
    product4 = ProductIndexModel(
        id="prod4", created_at=base_date, name="Watch", price=299.00
    )

    await ProductIndexModel.ainsert(product1, product2, product3, product4)

    # Act
    ProductIndexModel.init_class()
    found_models = await ProductIndexModel.afind(
        (ProductIndexModel.price >= 300.0) & (ProductIndexModel.price < 1000.0)
    )

    # Assert
    assert len(found_models) == 2
    assert product2 in found_models
    assert product3 in found_models
    assert product1 not in found_models
    assert product4 not in found_models

    # Cleanup
    await ProductIndexModel.adelete_index()


# NOTE: Testing string filtering with nested operators
@pytest.mark.asyncio
async def test_afind_with_complex_string_filtering_sanity(redis_client):
    # Arrange
    await ProductIndexModel.acreate_index()

    base_date = datetime(2024, 1, 1)
    product1 = ProductIndexModel(
        id="prod1", created_at=base_date, name="Ultra Laptop Pro", price=2500.0
    )
    product2 = ProductIndexModel(
        id="prod2", created_at=base_date, name="Basic Phone", price=299.0
    )
    product3 = ProductIndexModel(
        id="prod3", created_at=base_date, name="Pro Tablet", price=899.0
    )
    product4 = ProductIndexModel(
        id="prod4", created_at=base_date, name="Smart Watch Pro", price=399.0
    )

    await ProductIndexModel.ainsert(product1, product2, product3, product4)

    # Act - Complex filter: name contains "Pro" OR price < 400
    ProductIndexModel.init_class()
    expression1 = (ProductIndexModel.name == "Ultra Laptop Pro") | (
        ProductIndexModel.name == "Pro Tablet"
    )
    expression2 = ProductIndexModel.price < 400.0
    found_models = await ProductIndexModel.afind(expression1 | expression2)

    # Assert
    assert len(found_models) == 4  # All match either name contains Pro or price < 400
    assert product1 in found_models
    assert product2 in found_models
    assert product3 in found_models
    assert product4 in found_models

    # Cleanup
    await ProductIndexModel.adelete_index()


# NOTE: Testing filtering on inherited indexed fields (string id field)
@pytest.mark.asyncio
async def test_afind_with_inheritance_filtering_sanity(redis_client):
    # Arrange
    await UserIndexModel.acreate_index()
    await ProductIndexModel.acreate_index()

    base_date = datetime(2024, 1, 1)

    # Create UserIndexModel instances (inherits id and created_at from BaseIndexModel)
    user1 = UserIndexModel(
        id="admin_01", created_at=base_date, username="alice", email="alice@test.com"
    )
    user2 = UserIndexModel(
        id="user_02",
        created_at=base_date + timedelta(days=30),
        username="bob",
        email="bob@test.com",
    )
    user3 = UserIndexModel(
        id="user_03",
        created_at=base_date + timedelta(days=60),
        username="charlie",
        email="charlie@test.com",
    )

    # Create ProductIndexModel instances
    product1 = ProductIndexModel(
        id="prod_laptop", created_at=base_date, name="Laptop", price=1500.0
    )
    product2 = ProductIndexModel(
        id="prod_phone",
        created_at=base_date + timedelta(days=15),
        name="Phone",
        price=800.0,
    )
    product3 = ProductIndexModel(
        id="prod_tablet",
        created_at=base_date + timedelta(days=45),
        name="Tablet",
        price=600.0,
    )

    await UserIndexModel.ainsert(user1, user2, user3)
    await ProductIndexModel.ainsert(product1, product2, product3)

    # Act - Filter users by own username field (not inherited)
    UserIndexModel.init_class()
    users_found = await UserIndexModel.afind(UserIndexModel.id == "user_03")

    # Act - Filter products by own fields (combination of name and price)
    ProductIndexModel.init_class()
    products_found = await ProductIndexModel.afind(
        (ProductIndexModel.price > 500.0) & (ProductIndexModel.price < 1000.0)
    )

    # Assert
    assert len(users_found) == 1
    assert user3 in users_found

    assert len(products_found) == 2
    assert product2 in products_found
    assert product3 in products_found

    # Cleanup
    await UserIndexModel.adelete_index()
    await ProductIndexModel.adelete_index()


# NOTE: Testing datetime filtering with Index[datetime] fields
@pytest.mark.asyncio
async def test_afind_with_datetime_filtering_sanity(redis_client):
    # Arrange
    await UserIndexModel.acreate_index()

    base_date = datetime(2024, 1, 1, 10, 0, 0)
    cutoff_date = base_date + timedelta(days=6)

    user1 = UserIndexModel(
        id="user1",
        created_at=base_date,  # Before cutoff
        username="alice",
        email="alice@test.com",
    )
    user2 = UserIndexModel(
        id="user2",
        created_at=base_date + timedelta(days=20),  # After cutoff
        username="bob",
        email="bob@test.com",
    )
    user3 = UserIndexModel(
        id="user3",
        created_at=base_date + timedelta(days=5),  # Before cutoff
        username="charlie",
        email="charlie@test.com",
    )

    await UserIndexModel.ainsert(user1, user2, user3)

    # Act
    UserIndexModel.init_class()
    found_models = await UserIndexModel.afind(UserIndexModel.created_at < cutoff_date)

    # Assert
    assert len(found_models) == 2
    assert user1 in found_models
    assert user3 in found_models
    assert user2 not in found_models

    # Cleanup
    await UserIndexModel.adelete_index()


@pytest.mark.asyncio
async def test_afind_with_ne_expression_numeric_sanity(
    create_indices, inserted_test_models
):
    # Arrange
    IndexTestModel.init_class()

    # Act
    found_models = await IndexTestModel.afind(IndexTestModel.age != 30)

    # Assert
    assert len(found_models) == 3
    found_ages = {m.age for m in found_models}
    assert 30 not in found_ages
    assert 25 in found_ages
    assert 35 in found_ages
    assert 40 in found_ages


@pytest.mark.asyncio
async def test_afind_with_ne_expression_string_sanity(
    create_indices, inserted_test_models
):
    # Arrange
    IndexTestModel.init_class()

    # Act
    found_models = await IndexTestModel.afind(IndexTestModel.name != "Alice")

    # Assert
    assert len(found_models) == 3
    found_names = {m.name for m in found_models}
    assert "Alice" not in found_names
    assert "Bob" in found_names
    assert "Charlie" in found_names
    assert "David" in found_names


@pytest.mark.asyncio
async def test_afind_with_ne_expression_combined_with_and_sanity(
    create_indices, inserted_test_models
):
    # Arrange
    IndexTestModel.init_class()

    # Act - Find people who are not 30 and not Alice
    expression = (IndexTestModel.age != 30) & (IndexTestModel.name != "Alice")
    found_models = await IndexTestModel.afind(expression)

    # Assert - Should find Charlie (35) and David (40), both not age 30 and not Alice
    assert len(found_models) == 2
    found_names = {m.name for m in found_models}
    assert "Charlie" in found_names
    assert "David" in found_names


@pytest.mark.asyncio
async def test_afind_with_ne_expression_combined_with_or_sanity(
    create_indices, inserted_test_models
):
    # Arrange
    IndexTestModel.init_class()

    # Act - Find people who are not 30 OR not named Charlie
    expression = (IndexTestModel.age != 30) | (IndexTestModel.name != "Charlie")
    found_models = await IndexTestModel.afind(expression)

    # Assert - All 4 match (Alice: 25 not 30; Bob: not Charlie; Charlie: not 30; David: not Charlie)
    assert len(found_models) == 4


@pytest.mark.asyncio
async def test_afind_returns_empty_list_when_no_docs_match_expression_edge_case(
    create_indices,
):
    # Arrange - Insert models with ages 25, 30, 35
    models = [
        IndexTestModel(name="Alice", age=25, description="Engineer"),
        IndexTestModel(name="Bob", age=30, description="Manager"),
        IndexTestModel(name="Charlie", age=35, description="Designer"),
    ]
    await IndexTestModel.ainsert(*models)
    IndexTestModel.init_class()

    # Act - Search for models with age > 100 (none exist)
    found_models = await IndexTestModel.afind(IndexTestModel.age > 100)

    # Assert - Should return empty list
    assert found_models == []


@pytest.mark.asyncio
async def test_expression_field_create_filter_raises_bad_filter_error_sanity():
    # Act & Assert
    with pytest.raises(BadFilterError):
        await IndexTestModel.afind(IndexTestModel.name)


@pytest.mark.asyncio
async def test_afind_with_expression_handles_mixed_corrupted_data_comprehensive(
    create_indices,
):
    # Arrange
    models = [
        IndexTestModel(name="Alice", age=25, description="Engineer"),
        IndexTestModel(name="Bob", age=30, description="Manager"),
        IndexTestModel(name="Charlie", age=35, description="Designer"),
        IndexTestModel(name="David", age=40, description="Director"),
    ]
    await IndexTestModel.ainsert(*models)

    redis = IndexTestModel.Meta.redis
    lock_key = f"IndexTestModel:{uuid4()}:lock"
    await redis.set(lock_key, "lock_value")

    invalid_schema_key = f"IndexTestModel:{uuid4()}"
    await redis.json().set(invalid_schema_key, "$", {"age": "invalid", "name": 999})

    IndexTestModel.init_class()

    # Act
    found_models = await IndexTestModel.afind(
        (IndexTestModel.age > 25) & (IndexTestModel.age < 40)
    )

    # Assert
    assert len(found_models) == 2
    found_names = {m.name for m in found_models}
    assert "Bob" in found_names
    assert "Charlie" in found_names
