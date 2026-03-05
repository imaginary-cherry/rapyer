import pytest

from rapyer.types import RedisStr
from tests.models.complex_types import (
    ContainerModel,
    InnerRedisModel,
    OuterModelWithRedisNested,
)
from tests.models.inheritance_types import AdminUserModel
from tests.models.pickle_types import ModelWithUnserializableFields


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["initial_values", "update_values"],
    [
        [
            {"name": "John", "age": 25, "email": "john@test.com", "admin_level": 3},
            {"name": "Jane", "age": 30},
        ],
        [
            {
                "admin_level": 1,
                "is_super_admin": False,
                "name": "Admin",
                "email": "admin@test.com",
            },
            {"admin_level": 5, "is_super_admin": True},
        ],
        [
            {
                "email": "old@test.com",
                "backup_email": "backup@test.com",
                "name": "TestUser",
                "age": 35,
            },
            {"email": "new@test.com", "backup_email": "newbackup@test.com"},
        ],
    ],
)
async def test_aupdate_function__update_multiple_fields__values_updated_and_unchanged_fields_preserved_sanity(
    initial_values: dict, update_values: dict
):
    # Arrange
    instance = AdminUserModel(**initial_values)
    await instance.asave()
    original_data = instance.model_dump()

    # Act
    await instance.aupdate(**update_values)

    # Assert
    loaded_instance = await AdminUserModel.aget(instance.key)
    # Check updated fields
    for field_name, expected_value in update_values.items():
        assert getattr(loaded_instance, field_name) == expected_value
    # Check unchanged fields - all fields not in update_values should remain the same
    for field_name in AdminUserModel.model_fields.keys():
        if field_name not in update_values:
            assert getattr(loaded_instance, field_name) == original_data[field_name]


@pytest.mark.asyncio
async def test_aupdate_function__nested_field_operations__values_persisted_and_other_fields_unchanged_sanity():
    # Arrange
    instance = AdminUserModel(
        name="AdminUser",
        email="admin@test.com",
        age=40,
        admin_level=2,
        permissions=["read"],
        managed_users={"user1": "John"},
        is_super_admin=False,
    )
    await instance.asave()
    original_data = instance.model_dump()
    update_values = {
        "permissions": ["read", "write", "admin"],
        "managed_users": {"user1": "John", "user2": "Jane", "user3": "Bob"},
    }

    # Act
    await instance.aupdate(**update_values)

    # Assert
    loaded_instance = await AdminUserModel.aget(instance.key)
    # Check updated fields
    for field_name, expected_value in update_values.items():
        assert getattr(loaded_instance, field_name) == expected_value
    # Check unchanged fields - all fields not in update_values should remain the same
    for field_name in AdminUserModel.model_fields.keys():
        if field_name not in update_values:
            assert getattr(loaded_instance, field_name) == original_data[field_name]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["field_name", "initial_value"],
    [
        ["optional_field", "some_value"],
        ["backup_email", "backup@test.com"],
    ],
)
async def test_aupdate_function__update_field_to_none__value_updated_and_other_fields_unchanged_sanity(
    field_name: str, initial_value
):
    # Arrange
    instance = AdminUserModel(
        **{field_name: initial_value, "name": "TestUser", "email": "test@example.com"}
    )
    await instance.asave()
    original_data = instance.model_dump()
    update_values = {field_name: None}

    # Act
    await instance.aupdate(**update_values)

    # Assert
    loaded_instance = await AdminUserModel.aget(instance.key)
    # Check the updated field is None
    assert getattr(loaded_instance, field_name) is None
    # Check unchanged fields
    for other_field_name in AdminUserModel.model_fields.keys():
        if other_field_name != field_name:
            assert (
                getattr(loaded_instance, other_field_name)
                == original_data[other_field_name]
            )


@pytest.mark.asyncio
async def test_aupdate_function__update_non_redis_supported_types__values_serialized_and_updated_sanity():
    # Arrange
    instance = ModelWithUnserializableFields()
    await instance.asave()

    # Act
    await instance.aupdate(model_type=RedisStr, python_type=int)

    # Assert
    loaded_instance = await ModelWithUnserializableFields.aget(instance.key)
    # Check updated field - sets and types should be preserved through serialization
    assert loaded_instance.model_type == RedisStr
    assert loaded_instance.python_type == int


@pytest.mark.asyncio
async def test_aupdate_function__update_nested_model__nested_values_updated_and_other_fields_unchanged_sanity():
    # Arrange
    inner_redis = InnerRedisModel(
        tags=["tag1", "tag2"], metadata={"key1": "value1"}, counter=5
    )
    container = ContainerModel(inner_redis=inner_redis, description="test container")
    instance = OuterModelWithRedisNested(container=container, outer_data=[1, 2, 3])
    await instance.asave()
    original_data = instance.model_dump()

    # Act
    await instance.container.inner_redis.aupdate(
        tags=["updated1", "updated2"], counter=15
    )

    # Assert
    loaded_instance = await OuterModelWithRedisNested.aget(instance.key)
    # Check the updated inner redis model fields
    assert loaded_instance.container.inner_redis.tags == ["updated1", "updated2"]
    assert loaded_instance.container.inner_redis.counter == 15
    # Check unchanged inner redis model fields
    original_instance = OuterModelWithRedisNested(**original_data)
    assert (
        loaded_instance.container.inner_redis.metadata
        == original_instance.container.inner_redis.metadata
    )
    # Check unchanged container fields
    assert (
        loaded_instance.container.description == original_instance.container.description
    )
    # Check unchanged outer model fields
    assert loaded_instance.outer_data == original_instance.outer_data
