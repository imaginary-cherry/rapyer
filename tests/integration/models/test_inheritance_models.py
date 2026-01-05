from datetime import datetime

import pytest

from tests.models.inheritance_types import AdminUserModel, UserRole


@pytest.mark.asyncio
async def test_inheritance_models__default_values__save_load_verify_sanity():
    # Arrange
    instance = AdminUserModel()

    # Act
    await instance.asave()
    loaded_instance = await AdminUserModel.aget(instance.key)

    # Assert
    assert loaded_instance == instance


@pytest.mark.asyncio
async def test_inheritance_models__explicit_values__save_load_verify_sanity():
    # Arrange
    test_time = datetime(2023, 1, 1, 12, 0, 0)
    admin = AdminUserModel(
        name="John Doe",
        email="john@test.com",
        age=30,
        is_active=False,
        created_at=test_time,
        tags=["tag1", "tag2"],
        metadata={"key1": "value1", "key2": 42},
        role=UserRole.ADMIN,
        optional_field="test_optional",
        scores=[150, 250, 350],
        admin_level=5,
        permissions=["read", "write", "delete"],
        managed_users={"user1": "John", "user2": "Jane"},
        last_login=test_time,
        is_super_admin=True,
        admin_notes="Test admin notes",
        backup_email="backup@test.com",
        access_codes=[2001, 2002, 2003],
    )

    # Act
    await admin.asave()
    loaded_admin = await AdminUserModel.aget(admin.key)

    # Assert
    assert loaded_admin.name == "John Doe"
    assert loaded_admin.email == "john@test.com"
    assert loaded_admin.age == 30
    assert loaded_admin.is_active is False
    assert loaded_admin.created_at == test_time
    assert loaded_admin.tags == ["tag1", "tag2"]
    assert loaded_admin.metadata == {"key1": "value1", "key2": 42}
    assert loaded_admin.role == UserRole.ADMIN
    assert loaded_admin.optional_field == "test_optional"
    assert loaded_admin.scores == [150, 250, 350]
    assert loaded_admin.admin_level == 5
    assert loaded_admin.permissions == ["read", "write", "delete"]
    assert loaded_admin.managed_users == {"user1": "John", "user2": "Jane"}
    assert loaded_admin.last_login == test_time
    assert loaded_admin.is_super_admin is True
    assert loaded_admin.admin_notes == "Test admin notes"
    assert loaded_admin.backup_email == "backup@test.com"
    assert loaded_admin.access_codes == [2001, 2002, 2003]


@pytest.mark.asyncio
async def test_inheritance_models__admin_with_default_base_values__save_load_verify_sanity():
    # Arrange
    admin = AdminUserModel(
        admin_level=3, permissions=["read", "write", "admin"], is_super_admin=True
    )

    # Act
    await admin.asave()
    loaded_admin = await AdminUserModel.aget(admin.key)

    # Assert
    assert loaded_admin == admin


@pytest.mark.asyncio
async def test_inheritance_models__admin_inherited_field_operations__redis_actions_sanity():
    # Arrange
    admin = AdminUserModel(name="Test Admin", tags=["initial"])
    await admin.asave()

    # Act & Assert - Test list operations on inherited fields
    await admin.tags.aappend("new_tag")
    loaded_admin = await AdminUserModel.aget(admin.key)
    assert "new_tag" in loaded_admin.tags

    await admin.tags.aextend(["tag1", "tag2"])
    loaded_admin = await AdminUserModel.aget(admin.key)
    assert "tag1" in loaded_admin.tags
    assert "tag2" in loaded_admin.tags

    # Test dict operations on inherited fields
    await admin.metadata.aset_item("key1", "value1")
    loaded_admin = await AdminUserModel.aget(admin.key)
    assert loaded_admin.metadata["key1"] == "value1"


@pytest.mark.asyncio
async def test_inheritance_models__admin_model_operations__redis_actions_both_parent_and_child_fields_sanity():
    # Arrange
    admin = AdminUserModel(
        name="Admin User",
        tags=["admin_tag"],
        permissions=["read"],
        managed_users={"user1": "John"},
    )
    await admin.asave()

    # Act & Assert - Test operations on parent fields
    await admin.tags.aappend("parent_field_tag")
    loaded_admin = await AdminUserModel.aget(admin.key)
    assert "parent_field_tag" in loaded_admin.tags

    await admin.metadata.aset_item("parent_key", "parent_value")
    loaded_admin = await AdminUserModel.aget(admin.key)
    assert loaded_admin.metadata["parent_key"] == "parent_value"

    # Act & Assert - Test operations on child fields
    await admin.permissions.aappend("write")
    loaded_admin = await AdminUserModel.aget(admin.key)
    assert "write" in loaded_admin.permissions

    await admin.managed_users.aset_item("user2", "Jane")
    loaded_admin = await AdminUserModel.aget(admin.key)
    assert loaded_admin.managed_users["user2"] == "Jane"

    await admin.access_codes.aappend(9999)
    loaded_admin = await AdminUserModel.aget(admin.key)
    assert 9999 in loaded_admin.access_codes
