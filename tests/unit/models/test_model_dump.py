from tests.models.inheritance_types import AdminUserModel, UserRole
from tests.models.pickle_types import NonRedisDumpableModel
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


def test_int_enum_field_serializes_as_plain_int_sanity():
    # Arrange
    model = ModelWithIntEnumDefault(priority=IntPriority.HIGH, name="my_model")

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["priority"] == 3
    assert redis_data["name"] == "my_model"


def test_str_enum_field_serializes_as_plain_string_sanity():
    # Arrange
    model = ModelWithStrEnumDefault(status=StrStatus.INACTIVE, name="my_model")

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["status"] == "inactive"
    assert redis_data["name"] == "my_model"


def test_normal_dump_non_redis_fields__field_default_factory__sanity():
    # Arrange
    model = ModelWithStrEnumInList(name="my_model")

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["name"] == "my_model"
    assert redis_data["statuses"] == []


def test_str_enum_in_list_field_serializes_as_plain_strings_sanity():
    # Arrange
    model = ModelWithEnumCreatedByFactory()

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["status"] == "a"


def test_nested_model_with_enum_serializes_correctly_sanity():
    # Arrange
    inner = InnerModelWithEnum(status=StrStatus.INACTIVE)
    model = ModelWithNestedEnum(inner=inner, name="my_model")

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["inner"]["status"] == "inactive"
    assert redis_data["name"] == "my_model"


def test_inherited_enum_field_serializes_as_plain_string_sanity():
    # Arrange
    model = AdminUserModel(role=UserRole.ADMIN, name="admin_user")

    # Act
    redis_data = model.redis_dump()

    # Assert
    assert redis_data["role"] == "admin"
    assert redis_data["name"] == "admin_user"
