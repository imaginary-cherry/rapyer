from datetime import datetime

import pytest
import pytest_asyncio

from tests.models.collection_types import (
    SimpleListModel,
    SimpleDictModel,
    MixedTypesModel,
)
from tests.models.common import TaskStatus, Priority
from tests.models.complex_types import (
    NestedListModel,
    NestedDictModel,
    ListOfDictsModel,
    DictOfListsModel,
    OuterModel,
    InnerMostModel,
    MiddleModel,
)
from tests.models.inheritance_types import AdminUserModel, UserRole
from tests.models.pickle_types import NonRedisDumpableModel
from tests.models.redis_types import (
    DirectRedisStringModel,
    DirectRedisIntModel,
    DirectRedisBytesModel,
    DirectRedisListModel,
    DirectRedisDictModel,
    MixedDirectRedisTypesModel,
)
from tests.models.simple_types import (
    StrModel,
    IntModel,
    FloatModel,
    BoolModel,
    BytesModel,
    DatetimeModel,
    DatetimeTimestampModel,
    TaskModel,
)
from tests.models.unit_types import SimpleBytesModel
from tests.models.unknown_types import (
    ModelWithIntEnumDefault,
    IntPriority,
    ModelWithStrEnumDefault,
    StrStatus,
    ModelWithStrEnumInList,
    InnerModelWithEnum,
    ModelWithNestedEnum,
    ModelWithEnumCreatedByFactory,
)


@pytest_asyncio.fixture
async def prefer_json_dump():
    models = [
        StrModel,
        IntModel,
        FloatModel,
        BoolModel,
        BytesModel,
        DatetimeModel,
        DatetimeTimestampModel,
        TaskModel,
        DirectRedisStringModel,
        DirectRedisIntModel,
        DirectRedisBytesModel,
        DirectRedisListModel,
        DirectRedisDictModel,
        MixedDirectRedisTypesModel,
        NestedListModel,
        NestedDictModel,
        ListOfDictsModel,
        DictOfListsModel,
        OuterModel,
        ModelWithIntEnumDefault,
    ]
    original_preference = {}

    for model in models:
        original_preference[model] = model.Meta.prefer_normal_json_dump
        model.Meta.prefer_normal_json_dump = True
        model.model_rebuild(force=True)
    yield
    # Restore pickle serializers for all models
    for model in models:
        model.Meta.prefer_normal_json_dump = original_preference[model]
        model.model_rebuild(force=True)


@pytest.mark.asyncio
@pytest.mark.usefixtures("prefer_json_dump")
@pytest.mark.parametrize(
    ["model_instance", "expected_types"],
    [
        # Primitive str type
        [StrModel(name="test", description="hello"), {"name": str, "description": str}],
        # RedisStr type
        [DirectRedisStringModel(name="redis_string"), {"name": str}],
        # Primitive int type
        [IntModel(count=42, score=99), {"count": int, "score": int}],
        # RedisInt type
        [DirectRedisIntModel(count=100), {"count": int}],
        # Primitive float type with RedisFloat field
        [
            FloatModel(value=3.14, temperature=25.5),
            {"value": float, "temperature": float},
        ],
        # Primitive bool type
        [
            BoolModel(is_active=True, is_deleted=False),
            {"is_active": bool, "is_deleted": bool},
        ],
        # Primitive bytes type (gets pickled)
        [
            BytesModel(data=b"test_bytes", binary_content=b"content"),
            {"data": str, "binary_content": str},
        ],
        # RedisBytes type (gets pickled)
        [DirectRedisBytesModel(data=b"redis_bytes"), {"data": str}],
        # Primitive datetime type
        [
            DatetimeModel(
                created_at=datetime(2024, 1, 1, 12, 0, 0),
                updated_at=datetime(2024, 1, 2, 13, 0, 0),
            ),
            {"created_at": str, "updated_at": str},
        ],
        # RedisDatetimeTimestamp type
        [
            DatetimeTimestampModel(
                created_at=datetime(2024, 1, 1, 12, 0, 0),
                updated_at=datetime(2024, 1, 2, 13, 0, 0),
            ),
            {"created_at": float, "updated_at": float},
        ],
        # Primitive list type
        [SimpleListModel(items=["a", "b", "c"]), {"items": list}],
        # RedisList type
        [DirectRedisListModel(items=["x", "y", "z"]), {"items": list}],
        # Primitive dict type
        [SimpleDictModel(data={"key1": "val1", "key2": "val2"}), {"data": dict}],
        # RedisDict type
        [
            DirectRedisDictModel(metadata={"meta1": "value1", "meta2": "value2"}),
            {"metadata": dict},
        ],
        # Enum type
        [
            TaskModel(
                name="test_task", status=TaskStatus.RUNNING, priority=Priority.HIGH
            ),
            {"name": str, "status": str, "priority": str},
        ],
        # Mixed collection types with primitives
        [
            MixedTypesModel(
                str_list=["s1", "s2"],
                int_list=[1, 2, 3],
                bool_list=[True, False],
                bytes_list=[b"b1", b"b2"],
                str_dict={"k": "v"},
                int_dict={"n": 42},
                bool_dict={"flag": True},
                bytes_dict={"bin": b"data"},
            ),
            {
                "str_list": list,
                "int_list": list,
                "bool_list": list,
                "bytes_list": list,
                "mixed_list": list,
                "str_dict": dict,
                "int_dict": dict,
                "bool_dict": dict,
                "bytes_dict": dict,
                "mixed_dict": dict,
            },
        ],
        # Mixed Redis types
        [
            MixedDirectRedisTypesModel(
                name="mixed",
                count=5,
                active=False,
                tags=["tag1", "tag2"],
                config={"setting": 10},
            ),
            {"name": str, "count": int, "active": bool, "tags": list, "config": dict},
        ],
        # Nested list type
        [NestedListModel(nested_list=[["a", "b"], ["c", "d"]]), {"nested_list": list}],
        # Nested dict type
        [
            NestedDictModel(nested_dict={"outer": {"inner": "value"}}),
            {"nested_dict": dict},
        ],
        # List of dicts type
        [
            ListOfDictsModel(list_of_dicts=[{"k1": "v1"}, {"k2": "v2"}]),
            {"list_of_dicts": list},
        ],
        # Dict of lists type
        [
            DictOfListsModel(dict_of_lists={"list1": ["a", "b"], "list2": ["c"]}),
            {"dict_of_lists": dict},
        ],
        # Nested BaseModel
        [
            OuterModel(
                middle_model=MiddleModel(
                    inner_model=InnerMostModel(lst=["item"], counter=7),
                    tags=["tag"],
                    metadata={"key": "val"},
                ),
                user_data={"user": 1},
                items=[10, 20],
            ),
            {"middle_model": dict, "user_data": dict, "items": list},
        ],
    ],
)
async def test_redis_dump_all_types_with_json_sanity(model_instance, expected_types):
    # Arrange
    # Model instance already created in parameterize

    # Act
    result = model_instance.redis_dump()

    # Assert
    assert set(result.keys()) == set(expected_types.keys())
    for key, expected_type in expected_types.items():
        assert isinstance(
            result[key], expected_type
        ), f"Key '{key}' has wrong type: expected {expected_type}, got {type(result[key])}"


def test_model_dump_with_unsupported_redis_types_sanity():
    # Arrange
    model = NonRedisDumpableModel(set_field={"1"})

    # Act
    result = model.model_dump(mode="json")

    # Assert
    assert result["set_field"] == ["1"]


def test_model_dump_with_byte_model_sanity():
    # Arrange
    byt = b"hello this is great"
    model = SimpleBytesModel(data=byt)

    # Act
    result = model.model_dump(mode="json")

    # Assert
    assert result["data"] == byt.decode("utf-8")


@pytest.mark.asyncio
@pytest.mark.usefixtures("prefer_json_dump")
async def test_int_enum_field_serializes_as_plain_int_sanity():
    # Arrange
    model = ModelWithIntEnumDefault(priority=IntPriority.HIGH, name="my_model")

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["priority"] == 3
    assert redis_data["name"] == "my_model"


@pytest.mark.asyncio
@pytest.mark.usefixtures("prefer_json_dump")
async def test_str_enum_field_serializes_as_plain_string_sanity():
    # Arrange
    model = ModelWithStrEnumDefault(status=StrStatus.INACTIVE, name="my_model")

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["status"] == "inactive"
    assert redis_data["name"] == "my_model"


@pytest.mark.asyncio
@pytest.mark.usefixtures("prefer_json_dump")
async def test_normal_dump_non_redis_fields__field_default_factory__sanity():
    # Arrange
    model = ModelWithStrEnumInList(name="my_model")

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["name"] == "my_model"
    assert redis_data["statuses"] == []


@pytest.mark.asyncio
@pytest.mark.usefixtures("prefer_json_dump")
async def test_str_enum_in_list_field_serializes_as_plain_strings_sanity():
    # Arrange
    model = ModelWithEnumCreatedByFactory()

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["status"] == "a"


@pytest.mark.asyncio
@pytest.mark.usefixtures("prefer_json_dump")
async def test_nested_model_with_enum_serializes_correctly_sanity():
    # Arrange
    inner = InnerModelWithEnum(status=StrStatus.INACTIVE)
    model = ModelWithNestedEnum(inner=inner, name="my_model")

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["inner"]["status"] == "inactive"
    assert redis_data["name"] == "my_model"


@pytest.mark.asyncio
@pytest.mark.usefixtures("prefer_json_dump")
async def test_inherited_enum_field_serializes_as_plain_string_sanity():
    # Arrange
    model = AdminUserModel(role=UserRole.ADMIN, name="admin_user")

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["role"] == "admin"
    assert redis_data["name"] == "admin_user"
