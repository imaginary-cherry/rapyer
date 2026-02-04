import pytest

import rapyer
from tests.models.complex_types import InnerMostModel, MiddleModel, OuterModel
from tests.models.inheritance_types import AdminUserModel


@pytest.mark.asyncio
async def test_apipeline_field_assignment__different_nested_inherited_fields__all_persisted_correctly():
    # Arrange
    admin_model = AdminUserModel(
        name="initial_name",
        email="initial@email.com",
        age=30,
        tags=["initial_tag"],
        metadata={"initial_key": "initial_value"},
        scores=[100, 200],
        admin_level=1,
        permissions=["read"],
        managed_users={"user1": "John"},
        admin_notes="initial notes",
        access_codes=[1001],
    )
    outer_model = OuterModel(
        middle_model=MiddleModel(
            inner_model=InnerMostModel(lst=["initial_item"], counter=5),
            tags=["middle_tag"],
            metadata={"middle_key": "middle_value"},
        ),
        user_data={"existing_user": 100},
        items=[10, 20],
    )
    await rapyer.ainsert(admin_model, outer_model)

    # Act
    async with admin_model.apipeline() as admin_in_pipeline:
        # Inherited field assignments (AdminUserModel)
        admin_in_pipeline.name = "updated_name"
        admin_in_pipeline.email = "updated@email.com"
        admin_in_pipeline.age = 35
        admin_in_pipeline.tags = ["updated_tag1", "updated_tag2"]
        admin_in_pipeline.metadata = {"updated_key": "updated_value"}
        admin_in_pipeline.scores = [150, 250, 350]
        # Own field assignments (AdminUserModel)
        admin_in_pipeline.admin_level = 5
        admin_in_pipeline.permissions = ["read", "write", "admin"]
        admin_in_pipeline.managed_users = {"user1": "John", "user2": "Jane"}
        admin_in_pipeline.admin_notes = "updated notes"
        admin_in_pipeline.access_codes = [2001, 2002]

        # Load outer_model into same pipeline for nested field assignments
        outer_in_pipeline = await OuterModel.aget(outer_model.key)
        outer_in_pipeline.items = [30, 40, 50]
        outer_in_pipeline.user_data = {"new_user": 200}
        outer_in_pipeline.middle_model = MiddleModel(
            inner_model=InnerMostModel(lst=["new_item1", "new_item2"], counter=10),
            tags=["new_middle_tag"],
            metadata={"new_middle_key": "new_middle_value"},
        )

        # Verify atomicity - changes NOT visible yet
        loaded_admin = await AdminUserModel.aget(admin_model.key)
        loaded_outer = await OuterModel.aget(outer_model.key)
        assert loaded_admin.name == "initial_name"
        assert loaded_admin.admin_level == 1
        assert loaded_outer.items == [10, 20]

    # Assert
    final_admin, final_outer = await rapyer.afind(admin_model.key, outer_model.key)

    # Verify inherited fields
    assert final_admin.name == "updated_name"
    assert final_admin.email == "updated@email.com"
    assert final_admin.age == 35
    assert final_admin.tags == ["updated_tag1", "updated_tag2"]
    assert final_admin.metadata == {"updated_key": "updated_value"}
    assert final_admin.scores == [150, 250, 350]

    # Verify own fields
    assert final_admin.admin_level == 5
    assert final_admin.permissions == ["read", "write", "admin"]
    assert final_admin.managed_users == {"user1": "John", "user2": "Jane"}
    assert final_admin.admin_notes == "updated notes"
    assert final_admin.access_codes == [2001, 2002]

    # Verify top-level fields
    assert final_outer.items == [30, 40, 50]
    assert final_outer.user_data == {"new_user": 200}

    # Verify nested fields
    assert final_outer.middle_model.tags == ["new_middle_tag"]
    assert final_outer.middle_model.metadata == {"new_middle_key": "new_middle_value"}
    assert final_outer.middle_model.inner_model.lst == ["new_item1", "new_item2"]
    assert final_outer.middle_model.inner_model.counter == 10
