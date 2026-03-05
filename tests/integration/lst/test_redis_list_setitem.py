import pytest

from rapyer import AtomicRedisModel
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.string import RedisStr
from tests.models.collection_types import (
    BaseModelListModel,
    DictListModel,
    IntListModel,
    StrListModel,
)
from tests.models.common import NestedConfig, Product, UserProfile


@pytest.fixture
def int_list_model_with_items():
    return IntListModel(items=[0, 0, 0])


@pytest.fixture
def str_list_model_with_items():
    return StrListModel(items=["", "", ""])


@pytest.fixture
def dict_list_model_with_items():
    return DictListModel(items=[{}, {}, {}])


@pytest.fixture
def basemodel_list_model_with_users():
    model = BaseModelListModel()
    model.users = [None, None, None]
    return model


@pytest.fixture
def basemodel_list_model_with_products():
    model = BaseModelListModel()
    model.products = [
        Product(name="hi", price=100, in_stock=True),
        Product(name="hi", price=101, in_stock=False),
    ]
    return model


@pytest.fixture
def basemodel_list_model_with_configs():
    model = BaseModelListModel()
    model.configs = [
        NestedConfig(
            settings={"theme": "light", "lang": "en"}, options=["auto-save", "backup"]
        ),
        NestedConfig(
            settings={"theme": "dark", "lang": "en"}, options=["auto-save", "backup"]
        ),
    ]
    return model


@pytest.fixture
def sample_user_profile():
    return UserProfile(name="John Doe", age=30, email="john@example.com")


@pytest.fixture
def sample_product():
    return Product(name="Laptop", price=999, in_stock=True)


@pytest.fixture
def sample_nested_config():
    return NestedConfig(settings={"theme": "dark"}, options=["auto-save"])


@pytest.mark.asyncio
async def test_redis_list_setitem_int_type_checking_sanity(int_list_model_with_items):
    # Arrange
    model = int_list_model_with_items
    await model.asave()

    # Act
    model.items[2] = 42

    # Assert
    assert isinstance(model.items[2], RedisInt)


@pytest.mark.asyncio
async def test_redis_list_setitem_str_type_checking_sanity(str_list_model_with_items):
    # Arrange
    model = str_list_model_with_items
    await model.asave()

    # Act
    model.items[2] = "test_string"

    # Assert
    assert isinstance(model.items[2], RedisStr)


@pytest.mark.asyncio
async def test_redis_list_setitem_dict_type_checking_sanity(dict_list_model_with_items):
    # Arrange
    model = dict_list_model_with_items
    await model.asave()

    # Act
    model.items[2] = {"key": "value"}

    # Assert
    assert isinstance(model.items[2], RedisDict)


@pytest.mark.parametrize(
    "index,test_value",
    [
        [0, 100],
        [1, 200],
        [2, 300],
    ],
)
@pytest.mark.asyncio
async def test_redis_list_setitem_int_operations_sanity(index, test_value):
    # Arrange
    model = IntListModel(items=[0, 0, 0])
    await model.asave()

    # Act
    model.items[index] = test_value + 50
    await model.items[index].asave()

    # Assert
    fresh_model = IntListModel()
    fresh_model.pk = model.pk
    fresh_model.items = await fresh_model.items.aload()
    # After loading, items are regular Python types, not Redis types
    assert fresh_model.items[index] == test_value + 50


@pytest.mark.parametrize(
    "index,test_value",
    [
        [0, "hello"],
        [1, "world"],
        [2, "test"],
    ],
)
@pytest.mark.asyncio
async def test_redis_list_setitem_str_operations_sanity(index, test_value):
    # Arrange
    model = StrListModel(items=["", "", ""])
    await model.asave()

    # Act
    model.items[index] = test_value + "_modified"
    await model.items[index].asave()

    # Assert
    fresh_model = StrListModel()
    fresh_model.pk = model.pk
    fresh_model.items = await fresh_model.items.aload()
    # After loading, items are regular Python types, not Redis types
    assert fresh_model.items[index] == test_value + "_modified"


@pytest.mark.parametrize(
    "index,test_value",
    [
        [0, {"key1": "value1"}],
        [1, {"key2": "value2"}],
        [2, {"key3": "value3"}],
    ],
)
@pytest.mark.asyncio
async def test_redis_list_setitem_dict_operations_sanity(index, test_value):
    # Arrange
    model = DictListModel(items=[{}, {}, {}])
    await model.asave()

    # Act
    model.items[index] = test_value
    await model.asave()  # Save current state to Redis before update
    await model.items[index].aupdate(**{"new_key": "new_value"})

    # Assert
    fresh_model = DictListModel()
    fresh_model.pk = model.pk
    fresh_model.items = await fresh_model.items.aload()
    # After loading, items are regular Python types, not Redis types
    expected_dict = {**test_value, "new_key": "new_value"}
    assert fresh_model.items[index] == expected_dict


@pytest.mark.asyncio
async def test_redis_list_setitem_int_arithmetic_operations_sanity():
    # Arrange
    model = IntListModel(items=[0, 0, 0])
    await model.asave()

    # Act
    model.items[1] = 50

    # Assert
    assert model.items[1] + 10 == 60
    assert model.items[1] - 5 == 45
    assert model.items[1] * 2 == 100
    assert model.items[1] == 50


@pytest.mark.asyncio
async def test_redis_list_setitem_str_operations_edge_case():
    # Arrange
    model = StrListModel(items=["", "", ""])
    await model.asave()

    # Act
    model.items[0] = "test"

    # Assert
    assert model.items[0] + "_suffix" == "test_suffix"
    assert model.items[0].upper() == "TEST"
    assert len(model.items[0]) == 4


@pytest.mark.asyncio
async def test_redis_list_setitem_dict_key_access_edge_case():
    # Arrange
    model = DictListModel(items=[{}, {}, {}])
    await model.asave()

    # Act
    model.items[2] = {"test_key": "test_value", "another_key": "another_value"}

    # Assert
    assert model.items[2]["test_key"] == "test_value"
    assert model.items[2]["another_key"] == "another_value"
    assert len(model.items[2]) == 2


@pytest.mark.asyncio
async def test_redis_list_setitem_redis_field_paths_sanity():
    # Arrange
    model = IntListModel(items=[0, 0, 0])
    await model.asave()

    # Act
    model.items[1] = 42

    # Assert
    assert model.items[1].key == model.key
    assert model.items[1].field_path == ".items[1]"
    assert model.items[1].json_path == "$.items[1]"


@pytest.mark.asyncio
async def test_redis_list_setitem_multiple_indices_sanity():
    # Arrange
    model = IntListModel(items=[0, 0, 0, 0, 0])
    await model.asave()

    # Act
    model.items[0] = 10
    model.items[2] = 20
    model.items[4] = 30

    # Assert
    assert model.items[0] == 10
    assert model.items[1] == 0
    assert model.items[2] == 20
    assert model.items[3] == 0
    assert model.items[4] == 30


@pytest.mark.asyncio
async def test_redis_list_setitem_persistence_across_instances_edge_case():
    # Arrange
    model1 = IntListModel(items=[1, 2, 3])
    await model1.asave()

    # Act
    model1.items[1] = 99
    await model1.items[1].asave()

    # Assert
    model2 = IntListModel()
    model2.pk = model1.pk
    model2.items = await model2.items.aload()
    # After loading, items are regular Python types, not Redis types
    assert model2.items[1] == 99


@pytest.mark.asyncio
async def test_redis_list_setitem_basemodel_products_type_checking_sanity(
    basemodel_list_model_with_products, sample_product
):
    # Arrange
    model = basemodel_list_model_with_products
    await model.asave()
    test_value = sample_product

    # Act
    model.products[1] = test_value

    # Assert - should be a Redis BaseModel type
    list_item = model.products[1]
    assert isinstance(list_item, AtomicRedisModel)
    assert list_item.name == test_value.name
    assert list_item.price == test_value.price
    assert list_item.in_stock == test_value.in_stock


@pytest.mark.asyncio
async def test_redis_list_setitem_basemodel_configs_type_checking_sanity(
    basemodel_list_model_with_configs, sample_nested_config
):
    # Arrange
    model = basemodel_list_model_with_configs
    await model.asave()
    test_value = sample_nested_config

    # Act
    model.configs[1] = test_value

    # Assert - should be a Redis BaseModel type
    list_item = model.configs[1]
    assert isinstance(list_item, AtomicRedisModel)
    assert list_item.settings == test_value.settings
    assert list_item.options == test_value.options


@pytest.mark.asyncio
async def test_redis_list_setitem_basemodel_redis_operations_sanity():
    # Arrange
    model = BaseModelListModel()
    model.users = [UserProfile(name="Ori", age=2, email="Myemail")]
    await model.asave()

    user = UserProfile(name="Alice", age=25, email="alice@example.com")

    # Act
    model.users[0] = user

    # Assert - the setitem should create a Redis BaseModel
    assert isinstance(model.users[0], AtomicRedisModel)

    # Check that the data is preserved
    assert model.users[0].name == "Alice"
    assert model.users[0].age == 25
    assert model.users[0].email == "alice@example.com"

    # Check that we can modify the fields
    model.users[0].age = 26
    assert model.users[0].age == 26


@pytest.mark.asyncio
async def test_redis_list_setitem_basemodel_field_paths_sanity():
    # Arrange
    model = BaseModelListModel(
        products=[
            Product(name="Ori", price=2, in_stock=True),
            Product(name="Banan", price=2, in_stock=False),
        ]
    )
    await model.asave()

    product = Product(name="Phone", price=699, in_stock=False)

    # Act
    model.products[1] = product

    # Assert - BaseModels have different field path structure
    assert model.products[1].key == model.key  # Same Redis key as parent

    # Check the inst_field_conf for proper field path
    if hasattr(model.products[1], "inst_field_conf"):
        assert model.products[1].inst_field_conf.field_name == "products[1]"


@pytest.mark.asyncio
async def test_redis_list_setitem_basemodel_nested_operations_sanity():
    # Arrange
    model = BaseModelListModel(configs=[NestedConfig(settings={}, options=[])])
    await model.asave()

    config = NestedConfig(
        settings={"theme": "light", "lang": "en"}, options=["auto-save", "backup"]
    )

    # Act
    model.configs[0] = config

    # Assert - the setitem should create a Redis BaseModel with nested fields
    assert isinstance(model.configs[0], AtomicRedisModel)
    assert model.configs[0].settings == {"theme": "light", "lang": "en"}
    assert model.configs[0].options == ["auto-save", "backup"]

    # Check that we can modify nested fields (though save/load may not work correctly)
    model.configs[0].settings["theme"] = "dark"
    assert model.configs[0].settings["theme"] == "dark"

    model.configs[0].options.append("sync")
    assert len(model.configs[0].options) == 3
    assert "sync" in model.configs[0].options


@pytest.mark.asyncio
async def test_redis_list_setitem_basemodel_multiple_items_sanity():
    # Arrange
    model = BaseModelListModel(
        users=[
            UserProfile(name="Temp", age=0, email="asdfa"),
            UserProfile(name="Temp", age=0, email="asdfa"),
            UserProfile(name="Temp", age=0, email="asdfa"),
        ]
    )
    await model.asave()

    users = [
        UserProfile(name="User1", age=20, email="user1@example.com"),
        UserProfile(name="User2", age=30, email="user2@example.com"),
        UserProfile(name="User3", age=40, email="user3@example.com"),
    ]

    # Act
    for i, user in enumerate(users):
        model.users[i] = user

    # Assert - all items should be Redis BaseModels
    assert len(model.users) == 3
    for i, expected_user in enumerate(users):
        actual_user = model.users[i]
        assert isinstance(actual_user, AtomicRedisModel)
        assert actual_user.name == expected_user.name
        assert actual_user.age == expected_user.age
        assert actual_user.email == expected_user.email


@pytest.mark.asyncio
async def test_redis_list_setitem_basemodel_field_access_edge_case():
    # Arrange
    model = BaseModelListModel(
        products=[
            Product(name="Ori", price=2, in_stock=True),
            Product(name="Or2i", price=2, in_stock=True),
        ]
    )
    await model.asave()

    product = Product(name="Tablet", price=399, in_stock=True)

    # Act
    model.products[1] = product

    # Assert - verify we can access and modify all fields
    assert isinstance(model.products[1], AtomicRedisModel)
    assert model.products[1].name == "Tablet"
    assert model.products[1].price == 399
    # May be 1 instead of True due to Redis conversion
    assert model.products[1].in_stock == True

    # Modify fields
    model.products[1].name = "Updated Tablet"
    model.products[1].price = 299
    model.products[1].in_stock = False

    assert model.products[1].name == "Updated Tablet"
    assert model.products[1].price == 299
    # May be 0 instead of False due to Redis conversion
    assert model.products[1].in_stock == False


@pytest.mark.asyncio
async def test_redis_list_apop_after_clear_sanity():
    # Arrange
    model = StrListModel(items=["item1", "item2", "item3"])
    await model.asave()

    # Act
    model.items = []
    await model.asave()
    await model.items.aappend("new_item")

    popped_value = await model.items.apop()

    # Assert
    assert popped_value == "new_item" or popped_value == '"new_item"'


@pytest.mark.asyncio
async def test_redis_list__apop_empty_redis__check_default_returned_sanity():
    # Arrange
    model = StrListModel()
    await model.asave()

    # Act
    result = await model.items.apop()

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_redis_list__apop_for_models__sanity():
    # Arrange
    user = UserProfile(name="Ori", age=2, email="Myemail")
    model = BaseModelListModel(users=[user])
    await model.asave()

    # Act
    result = await model.users.apop()

    # Assert
    assert result.model_dump() == user.model_dump()
