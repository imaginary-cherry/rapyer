import pytest

from tests.models.collection_types import ProductListModel, UserListModel
from tests.models.common import Product, User


@pytest.fixture
def sample_users():
    return [
        User(name="Alice", id=25, email="alice@example.com"),
        User(name="Bob", id=30, email="bob@example.com"),
        User(name="Charlie", id=35, email="charlie@example.com"),
    ]


@pytest.fixture
def sample_products():
    return [
        Product(name="Laptop", price=999, in_stock=True),
        Product(name="Mouse", price=25, in_stock=False),
        Product(name="Keyboard", price=75, in_stock=True),
    ]


@pytest.mark.parametrize(
    "user_data",
    [
        User(name="Test User", id=20, email="test@example.com"),
        User(name="Another User", id=40, email="another@example.com"),
    ],
)
@pytest.mark.asyncio
async def test_redis_list_aappend_basemodel_operations_sanity(user_data):
    # Arrange
    model = UserListModel()
    await model.asave()

    # Act
    await model.users.aappend(user_data)

    # Assert
    fresh_model = UserListModel()
    fresh_model.pk = model.pk
    loaded_users = await fresh_model.users.aload()
    assert len(loaded_users) == 1
    assert loaded_users[0].name == user_data.name
    assert loaded_users[0].id == user_data.id
    assert loaded_users[0].email == user_data.email


@pytest.mark.asyncio
async def test_redis_list_aextend_basemodel_operations_sanity(sample_users):
    # Arrange
    model = UserListModel()
    await model.asave()

    # Act
    await model.users.aextend(sample_users)

    # Assert
    fresh_model = UserListModel()
    fresh_model.pk = model.pk
    loaded_users = await fresh_model.users.aload()
    assert len(loaded_users) == len(sample_users)
    for i, expected_user in enumerate(sample_users):
        assert loaded_users[i].name == expected_user.name
        assert loaded_users[i].id == expected_user.id
        assert loaded_users[i].email == expected_user.email


@pytest.mark.asyncio
async def test_redis_list_apop_basemodel_operations_sanity(sample_users):
    # Arrange
    model = UserListModel(users=sample_users)
    await model.asave()

    # Act
    popped_user = await model.users.apop()

    # Assert
    expected_user = sample_users[-1]  # Last user should be popped
    assert popped_user.name == expected_user.name
    assert popped_user.id == expected_user.id
    assert popped_user.email == expected_user.email

    # Verify the user was removed from Redis
    fresh_model = UserListModel()
    fresh_model.pk = model.pk
    loaded_users = await fresh_model.users.aload()
    assert len(loaded_users) == len(sample_users) - 1


@pytest.mark.parametrize(
    "insert_index",
    [0, 1, 2],
)
@pytest.mark.asyncio
async def test_redis_list_ainsert_basemodel_operations_sanity(
    sample_users, insert_index
):
    # Arrange
    model = UserListModel(users=sample_users)
    await model.asave()
    new_user = User(name="Inserted User", id=28, email="inserted@example.com")

    # Act
    await model.users.ainsert(insert_index, new_user)

    # Assert
    fresh_model = UserListModel()
    fresh_model.pk = model.pk
    loaded_users = await fresh_model.users.aload()
    assert len(loaded_users) == len(sample_users) + 1
    assert loaded_users[insert_index].name == new_user.name
    assert loaded_users[insert_index].id == new_user.id
    assert loaded_users[insert_index].email == new_user.email


@pytest.mark.asyncio
async def test_redis_list_aclear_basemodel_operations_sanity(sample_users):
    # Arrange
    model = UserListModel(users=sample_users)
    await model.asave()

    # Act
    await model.users.aclear()

    # Assert
    fresh_model = UserListModel()
    fresh_model.pk = model.pk
    loaded_users = await fresh_model.users.aload()
    assert len(loaded_users) == 0


@pytest.mark.asyncio
async def test_redis_list_multiple_operations_basemodel_sanity(sample_products):
    # Arrange
    model = ProductListModel()
    await model.asave()

    # Act
    await model.products.aextend(sample_products[:2])
    new_product = Product(name="Monitor", price=300, in_stock=True)
    await model.products.aappend(new_product)
    await model.products.ainsert(1, Product(name="Webcam", price=50, in_stock=False))

    # Assert
    fresh_model = ProductListModel()
    fresh_model.pk = model.pk
    loaded_products = await fresh_model.products.aload()
    assert len(loaded_products) == 4

    # Verify the first product
    assert loaded_products[0].name == sample_products[0].name
    assert loaded_products[0].price == sample_products[0].price
    assert loaded_products[0].in_stock == sample_products[0].in_stock

    # Verify inserted product
    assert loaded_products[1].name == "Webcam"
    assert loaded_products[1].price == 50
    assert loaded_products[1].in_stock == False

    # Verify the second original product
    assert loaded_products[2].name == sample_products[1].name
    assert loaded_products[2].price == sample_products[1].price
    assert loaded_products[2].in_stock == sample_products[1].in_stock

    # Verify the appended product
    assert loaded_products[3].name == new_product.name
    assert loaded_products[3].price == new_product.price
    assert loaded_products[3].in_stock == new_product.in_stock


@pytest.mark.asyncio
async def test_redis_list_apop_empty_list_basemodel_edge_case():
    # Arrange
    model = UserListModel()
    await model.asave()

    # Act
    result = await model.users.apop()

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_redis_list_operations_preserve_basemodel_data_integrity_sanity():
    # Arrange
    model = UserListModel()
    await model.asave()
    complex_user = User(
        name="Complex User", id=45, email="complex.user+test@example.com"
    )

    # Act
    await model.users.aappend(complex_user)
    await model.users.aextend(
        [
            User(name="User 1", id=20, email="user1@test.com"),
            User(name="User 2", id=30, email="user2@test.com"),
        ]
    )

    # Assert
    fresh_model = UserListModel()
    fresh_model.pk = model.pk
    loaded_users = await fresh_model.users.aload()

    # Verify complex user data integrity
    assert loaded_users[0].name == complex_user.name
    assert loaded_users[0].id == complex_user.id
    assert loaded_users[0].email == complex_user.email

    # Verify extended users
    assert len(loaded_users) == 3
    assert loaded_users[1].name == "User 1"
    assert loaded_users[2].name == "User 2"


@pytest.mark.asyncio
async def test_redis_list_basemodel_operations_after_model_creation_set_load_sanity():
    # Arrange
    initial_users = [
        User(name="Initial User 1", id=25, email="init1@example.com"),
        User(name="Initial User 2", id=30, email="init2@example.com"),
    ]
    model = UserListModel(users=initial_users)
    await model.asave()

    # Act - Perform operations after model creation
    await model.users.aappend(
        User(name="Appended User", id=35, email="append@example.com")
    )
    popped_user = await model.users.apop(0)  # Pop first user
    await model.users.ainsert(
        0, User(name="Inserted User", id=40, email="insert@example.com")
    )

    # Assert
    fresh_model = UserListModel()
    fresh_model.pk = model.pk
    loaded_users = await fresh_model.users.aload()

    # Should have: Inserted User, Initial User 2, Appended User
    assert len(loaded_users) == 3
    assert loaded_users[0].name == "Inserted User"
    assert loaded_users[1].name == "Initial User 2"
    assert loaded_users[2].name == "Appended User"

    # Verify the popped user was the first initial user
    assert popped_user.name == "Initial User 1"
