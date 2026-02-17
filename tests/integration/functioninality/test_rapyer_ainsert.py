from datetime import datetime

import pytest
import rapyer
from tests.models.collection_types import (
    ListModel,
    DictModel,
    ComprehensiveTestModel,
    BaseModelListModel,
)
from tests.models.common import (
    UserProfile,
    Product,
    NestedConfig,
    UserWithKeyModel,
    EventWithDatetimeKeyModel,
)
from tests.models.complex_types import (
    OuterModel,
    TestRedisModel,
    MiddleModel,
    InnerMostModel,
    DuplicateMiddleModel,
    DuplicateInnerMostModel,
)
from tests.models.inheritance_types import BaseUserModel, AdminUserModel, UserRole
from tests.models.pickle_types import ModelWithUnserializableFields
from tests.models.redis_types import DirectRedisStringModel, MixedDirectRedisTypesModel
from tests.models.simple_types import (
    StrModel,
    IntModel,
    BoolModel,
    BytesModel,
    DatetimeModel,
)


@pytest.mark.asyncio
async def test_ainsert_multiple_different_types_sanity():
    # Arrange
    str_model = StrModel(name="bulk_test_user", description="bulk description")
    int_model = IntModel(count=99, score=200)
    bool_model = BoolModel(is_active=False, is_deleted=True)
    bytes_model = BytesModel(data=b"bulk_data", binary_content=b"bulk_binary")
    datetime_model = DatetimeModel()
    list_model = ListModel(items=["bulk1", "bulk2"], numbers=[10, 20, 30])
    dict_model = DictModel(data={"bulk_key": "bulk_value"}, config={"bulk_setting": 50})

    comprehensive_model = ComprehensiveTestModel(
        tags=["bulk_tag1", "bulk_tag2"],
        metadata={"bulk": "metadata"},
        name="bulk_comprehensive",
        counter=25,
    )

    nested_model = OuterModel(
        middle_model=MiddleModel(
            inner_model=InnerMostModel(lst=["bulk", "nested", "values"], counter=100),
            tags=["bulk", "middleware"],
            metadata={"bulk_level": "middle"},
        ),
        user_data={"bulk_users": 500},
        items=[100, 200, 300],
    )

    redis_model = TestRedisModel(
        middle_model=DuplicateMiddleModel(
            inner_model=DuplicateInnerMostModel(
                names=["bulk_alice", "bulk_bob"],
                scores={"bulk_math": 100},
                counter=50,
            ),
            tags=["bulk", "redis"],
            metadata={"bulk_version": "2.0"},
        ),
        user_data={"bulk_active": 1000},
        items=[500, 600],
        description="bulk_redis_model",
    )

    direct_redis_model = DirectRedisStringModel(name="bulk_redis_string")

    mixed_redis_model = MixedDirectRedisTypesModel(
        name="bulk_mixed",
        count=999,
        active=False,
        tags=["bulk_redis1"],
        config={"bulk_config": 1000},
    )

    basemodel_list_model = BaseModelListModel(
        users=[
            UserProfile(name="BulkUser1", age=40, email="bulk1@test.com"),
            UserProfile(name="BulkUser2", age=45, email="bulk2@test.com"),
        ],
        products=[
            Product(name="bulk_laptop", price=2000, in_stock=True),
        ],
        configs=[
            NestedConfig(
                settings={"bulk_theme": "light"},
                options=["bulk_option1"],
            )
        ],
    )

    base_user_model = BaseUserModel(
        name="bulk_base_user",
        email="bulk_base@example.com",
        age=50,
        is_active=True,
        tags=["bulk_tag"],
        metadata={"bulk": "user"},
        role=UserRole.USER,
        scores=[100, 90, 80],
    )

    admin_user_model = AdminUserModel(
        name="bulk_admin",
        email="bulk_admin@example.com",
        age=55,
        is_active=True,
        tags=["bulk_admin"],
        metadata={"bulk": "admin"},
        role=UserRole.ADMIN,
        admin_level=10,
        permissions=["all"],
        managed_users={"bulk_user": "Bulk User"},
        is_super_admin=True,
    )

    pickle_model = ModelWithUnserializableFields(value=999, python_type=AdminUserModel)

    user_key_model = UserWithKeyModel(
        user_id="bulk_user_key_999",
        name="Bulk Key User",
        email="bulkkey@example.com",
        age=60,
    )

    event_model = EventWithDatetimeKeyModel(
        created_at=datetime(2024, 12, 25, 10, 0, 0),
        event_name="Bulk Event",
        description="Bulk event description",
        duration_minutes=120,
    )

    all_models = [
        str_model,
        int_model,
        bool_model,
        bytes_model,
        datetime_model,
        list_model,
        dict_model,
        comprehensive_model,
        nested_model,
        redis_model,
        direct_redis_model,
        mixed_redis_model,
        basemodel_list_model,
        base_user_model,
        admin_user_model,
        pickle_model,
        user_key_model,
        event_model,
    ]

    # Act
    await rapyer.ainsert(*all_models)

    # Assert
    for model in all_models:
        retrieved_model = await rapyer.aget(model.key)
        assert retrieved_model == model
