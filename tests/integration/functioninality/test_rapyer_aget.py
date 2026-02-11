from datetime import datetime

import pytest
import rapyer
from rapyer.errors import KeyNotFound
from rapyer.fields import RapyerKey
from rapyer.fields import RapyerKey
from tests.models.collection_types import (
    ListModel,
    DictModel,
    ComprehensiveTestModel,
    BaseModelListModel,
    BaseModelDictModel,
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
    OuterModelWithRedisNested,
    MiddleModel,
    InnerMostModel,
    TripleNestedModel,
    ComplexNestedModel,
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


@pytest.mark.parametrize(
    ["model_instance"],
    [
        [StrModel(name="test_user", description="test description")],
        [IntModel(count=42, score=100)],
        [BoolModel(is_active=True, is_deleted=False)],
        [BytesModel(data=b"test_data", binary_content=b"binary_test")],
        [DatetimeModel()],
        [ListModel(items=["item1", "item2"], numbers=[1, 2, 3])],
        [DictModel(data={"key1": "value1"}, config={"setting1": 10})],
        [
            ComprehensiveTestModel(
                tags=["tag1", "tag2"],
                metadata={"key": "value"},
                name="comprehensive",
                counter=5,
            )
        ],
        [
            OuterModel(
                middle_model=MiddleModel(
                    inner_model=InnerMostModel(
                        lst=["nested", "list", "values"], counter=42
                    ),
                    tags=["middleware", "complex", "nested"],
                    metadata={"level": "middle", "type": "nested", "depth": "2"},
                ),
                user_data={"active_users": 150, "total_sessions": 1200},
                items=[10, 20, 30, 40, 50],
            )
        ],
        [
            TestRedisModel(
                middle_model=DuplicateMiddleModel(
                    inner_model=DuplicateInnerMostModel(
                        names=["alice", "bob", "charlie"],
                        scores={"math": 95, "science": 87, "english": 92},
                        counter=15,
                    ),
                    tags=["test", "redis", "complex"],
                    metadata={
                        "version": "1.0",
                        "environment": "test",
                        "type": "duplicate",
                    },
                ),
                user_data={"active": 456, "pending": 123, "inactive": 78},
                items=[30, 40, 50, 60, 70],
                description="complex_test_redis_model",
            )
        ],
        [DirectRedisStringModel(name="redis_string_test")],
        [
            MixedDirectRedisTypesModel(
                name="mixed_test",
                count=99,
                active=True,
                tags=["redis1", "redis2"],
                config={"config_key": 100},
            )
        ],
        # Complex nested models with BaseModel objects
        [
            BaseModelListModel(
                users=[
                    UserProfile(name="Alice", age=30, email="alice@test.com"),
                    UserProfile(name="Bob", age=25, email="bob@test.com"),
                ],
                products=[
                    Product(name="laptop", price=1000, in_stock=True),
                    Product(name="mouse", price=25, in_stock=False),
                ],
                configs=[
                    NestedConfig(
                        settings={"theme": "dark", "lang": "en"},
                        options=["feature1", "feature2"],
                    )
                ],
            )
        ],
        [
            BaseModelDictModel(
                metadata={
                    "admin": UserProfile(name="Admin", age=35, email="admin@test.com"),
                    "guest": UserProfile(name="Guest", age=22, email="guest@test.com"),
                }
            )
        ],
        # Deeply nested models
        [
            OuterModelWithRedisNested(
                outer_data=[1, 2, 3, 4, 5],
            )
        ],
        # Triple nested complex structures
        [
            TripleNestedModel(
                triple_list=[
                    [["level1", "data1"], ["level1", "data2"]],
                    [["level2", "data1"], ["level2", "data2"], ["level2", "data3"]],
                    [["level3", "final"]],
                ],
                triple_dict={
                    "outer1": {
                        "middle1": {"inner1": "value1", "inner2": "value2"},
                        "middle2": {"inner3": "value3"},
                    },
                    "outer2": {
                        "middle3": {"inner4": "value4", "inner5": "value5"},
                        "middle4": {"inner6": "value6", "inner7": "value7"},
                    },
                },
            )
        ],
        # Complex multi-type nested structures
        [
            ComplexNestedModel(
                nested_list=[
                    ["group1", "item1", "item2"],
                    ["group2", "item3", "item4", "item5"],
                    ["group3", "item6"],
                ],
                nested_dict={
                    "config": {"theme": "dark", "language": "en"},
                    "settings": {"timeout": "30", "retries": "3"},
                    "features": {"advanced": "true", "beta": "false"},
                },
                list_of_dicts=[
                    {"name": "user1", "role": "admin"},
                    {"name": "user2", "role": "viewer"},
                    {"name": "user3", "role": "editor"},
                ],
                dict_of_lists={
                    "permissions": ["read", "write", "delete"],
                    "tags": ["important", "urgent", "review"],
                    "categories": ["finance", "operations", "hr"],
                },
            )
        ],
        # Inheritance models
        [
            BaseUserModel(
                name="base_user",
                email="base@example.com",
                age=28,
                is_active=True,
                tags=["tag1", "tag2", "tag3"],
                metadata={"level": "basic", "department": "IT"},
                role=UserRole.USER,
                optional_field="optional_value",
                scores=[95, 87, 92],
            )
        ],
        [
            AdminUserModel(
                name="admin_user",
                email="admin@example.com",
                age=35,
                is_active=True,
                tags=["admin", "supervisor"],
                metadata={"level": "senior", "department": "Management"},
                role=UserRole.ADMIN,
                admin_level=5,
                permissions=["read", "write", "delete", "admin"],
                managed_users={"user1": "John Doe", "user2": "Jane Smith"},
                is_super_admin=True,
                admin_notes="Senior administrator with full privileges",
                backup_email="admin.backup@example.com",
                access_codes=[2001, 2002, 2003],
            )
        ],
        # Models with picklable/unserializable fields
        [ModelWithUnserializableFields(value=123, python_type=AdminUserModel)],
        # Models with custom key annotations
        [
            UserWithKeyModel(
                user_id="custom_user_key_123",
                name="Key User",
                email="keyuser@example.com",
                age=32,
            )
        ],
        # Model with datetime key annotation
        [
            EventWithDatetimeKeyModel(
                created_at=datetime(2024, 12, 15, 9, 0, 0),
                event_name="Annual Conference 2024",
                description="Company-wide annual conference with technical sessions",
                duration_minutes=480,
            )
        ],
    ],
)
@pytest.mark.asyncio
async def test_rapyer_get_functionality_sanity(model_instance):
    # Arrange
    await model_instance.asave()
    redis_key = model_instance.key

    # Act
    retrieved_model = await rapyer.aget(redis_key)

    # Assert
    assert retrieved_model == model_instance
    assert isinstance(retrieved_model.key, RapyerKey)
    assert isinstance(retrieved_model.key, RapyerKey)


@pytest.mark.asyncio
async def test_rapyer_aget_with_key_without_class_name_edge_case():
    # Arrange
    key_without_class = "12345"  # No class name prefix

    # Act & Assert
    with pytest.raises(KeyNotFound) as exc_info:
        await rapyer.aget(key_without_class)
