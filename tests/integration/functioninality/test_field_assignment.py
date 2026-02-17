from datetime import datetime

import pytest
import pytest_asyncio
from pydantic import ValidationError
from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetime
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.string import RedisStr
from tests.models.collection_types import MixedTypesModel, StrDictModel
from tests.models.common import TaskStatus, Priority
from tests.models.complex_types import InnerMostModel, MiddleModel, OuterModel
from tests.models.simple_types import (
    NoneTestModel,
    BoolModel,
    BytesModel,
    DatetimeModel,
    TaskModel,
    IntModel,
    StrModel,
)

# Import models from centralized location
from tests.models.specialized import UserModel as BaseUserModel


@pytest_asyncio.fixture
async def mixed_model(redis_client):
    MixedTypesModel.Meta.redis = redis_client
    yield MixedTypesModel()


@pytest_asyncio.fixture
async def user_model_with_tags(redis_client):
    BaseUserModel.Meta.redis = redis_client
    yield BaseUserModel(tags=["initial", "tags"])


@pytest_asyncio.fixture
async def str_model_with_values(redis_client):
    StrModel.Meta.redis = redis_client
    yield StrModel(name="initial_name", description="initial_desc")


@pytest_asyncio.fixture
async def int_model_with_values(redis_client):
    IntModel.Meta.redis = redis_client
    yield IntModel(count=50, score=200)


@pytest_asyncio.fixture
async def bool_model_with_values(redis_client):
    BoolModel.Meta.redis = redis_client
    yield BoolModel(is_active=True, is_deleted=False)


@pytest_asyncio.fixture
async def bytes_model_with_values(redis_client):
    BytesModel.Meta.redis = redis_client
    yield BytesModel(data=b"initial_data", binary_content=b"initial_binary")


@pytest_asyncio.fixture
async def dict_model_with_values(redis_client):
    StrDictModel.Meta.redis = redis_client
    yield StrDictModel(metadata={"key1": "value1", "key2": "value2"})


@pytest_asyncio.fixture
async def none_model_with_values(redis_client):
    NoneTestModel.Meta.redis = redis_client
    yield NoneTestModel(optional_string="test", optional_int=42)


@pytest_asyncio.fixture
async def datetime_model_with_values(redis_client):
    DatetimeModel.Meta.redis = redis_client
    initial_datetime = datetime(2023, 1, 1, 12, 0, 0)
    yield DatetimeModel(created_at=initial_datetime, updated_at=initial_datetime)


@pytest_asyncio.fixture
async def task_model_with_values(redis_client):
    TaskModel.Meta.redis = redis_client
    yield TaskModel(
        name="test_task", status=TaskStatus.PENDING, priority=Priority.MEDIUM
    )


@pytest_asyncio.fixture
async def outer_model_with_values(redis_client):
    OuterModel.Meta.redis = redis_client
    inner_model = InnerMostModel(lst=["item1"], counter=5)
    middle_model = MiddleModel(
        inner_model=inner_model, tags=["tag1"], metadata={"key": "value"}
    )
    yield OuterModel(middle_model=middle_model, user_data={"user": 100}, items=[1, 2])


# Constructor initialization tests
@pytest.mark.asyncio
async def test_constructor_string_fields_converted_to_redis_types_sanity(
    str_model_with_values,
):
    # Arrange & Act (done in fixture)

    # Assert - fields initialized in constructor should be Redis types
    assert isinstance(str_model_with_values.name, RedisStr)
    assert isinstance(str_model_with_values.description, RedisStr)

    # Assert - values preserved
    assert str(str_model_with_values.name) == "initial_name"
    assert str(str_model_with_values.description) == "initial_desc"


@pytest.mark.asyncio
async def test_constructor_list_field_converted_to_redis_type_sanity(
    user_model_with_tags,
):
    # Arrange & Act (done in fixture)

    # Assert - field initialized in the constructor should be Redis type
    assert isinstance(user_model_with_tags.tags, RedisList)
    assert list(user_model_with_tags.tags) == ["initial", "tags"]


@pytest.mark.asyncio
async def test_constructor_int_fields_converted_to_redis_types_sanity(
    int_model_with_values,
):
    # Arrange & Act (done in fixture)

    # Assert - fields initialized in constructor should be Redis types
    assert isinstance(int_model_with_values.count, RedisInt)
    assert isinstance(int_model_with_values.score, RedisInt)

    # Assert - values preserved
    assert int(int_model_with_values.count) == 50
    assert int(int_model_with_values.score) == 200


@pytest.mark.asyncio
async def test_constructor_bool_fields_converted_to_redis_types_sanity(
    bool_model_with_values,
):
    # Arrange & Act (done in fixture)

    # Assert - fields initialized in constructor should be Redis types
    assert isinstance(bool_model_with_values.is_active, bool)
    assert isinstance(bool_model_with_values.is_deleted, bool)

    # Assert - values preserved
    assert bool(bool_model_with_values.is_active) is True
    assert bool(bool_model_with_values.is_deleted) is False


@pytest.mark.asyncio
async def test_constructor_bytes_fields_converted_to_redis_types_sanity(
    bytes_model_with_values,
):
    # Arrange & Act (done in fixture)

    # Assert - fields initialized in constructor should be Redis types
    assert isinstance(bytes_model_with_values.data, RedisBytes)
    assert isinstance(bytes_model_with_values.binary_content, RedisBytes)

    # Assert - values preserved
    assert bytes(bytes_model_with_values.data) == b"initial_data"
    assert bytes(bytes_model_with_values.binary_content) == b"initial_binary"


@pytest.mark.asyncio
async def test_constructor_dict_field_converted_to_redis_type_sanity(
    dict_model_with_values,
):
    # Arrange & Act (done in fixture)

    # Assert - field initialized in constructor should be Redis type
    assert isinstance(dict_model_with_values.metadata, RedisDict)
    assert dict(dict_model_with_values.metadata) == {"key1": "value1", "key2": "value2"}


# Post-construction assignment tests
@pytest.mark.asyncio
async def test_assignment_string_field_converts_to_redis_type_sanity(
    str_model_with_values,
):
    # Arrange & Act
    str_model_with_values.name = "updated_name"
    str_model_with_values.description = "updated_description"

    # Assert
    assert isinstance(str_model_with_values.name, RedisStr)
    assert isinstance(str_model_with_values.description, RedisStr)
    assert str(str_model_with_values.name) == "updated_name"
    assert str(str_model_with_values.description) == "updated_description"


@pytest.mark.asyncio
async def test_assignment_list_field_converts_to_redis_type_sanity(
    user_model_with_tags,
):
    # Arrange & Act
    user_model_with_tags.tags = ["python", "redis", "testing"]

    # Assert
    assert isinstance(user_model_with_tags.tags, RedisList)
    assert list(user_model_with_tags.tags) == ["python", "redis", "testing"]


@pytest.mark.asyncio
async def test_assignment_int_fields_convert_to_redis_types_sanity(
    int_model_with_values,
):
    # Arrange & Act
    int_model_with_values.count = 100
    int_model_with_values.score = 500

    # Assert
    assert isinstance(int_model_with_values.count, RedisInt)
    assert isinstance(int_model_with_values.score, RedisInt)
    assert int(int_model_with_values.count) == 100
    assert int(int_model_with_values.score) == 500


@pytest.mark.asyncio
async def test_assignment_bool_fields_convert_to_redis_types_sanity(
    bool_model_with_values,
):
    # Arrange & Act
    bool_model_with_values.is_active = False
    bool_model_with_values.is_deleted = True

    # Assert
    assert isinstance(bool_model_with_values.is_active, bool)
    assert isinstance(bool_model_with_values.is_deleted, bool)
    assert bool(bool_model_with_values.is_active) is False
    assert bool(bool_model_with_values.is_deleted) is True


@pytest.mark.asyncio
async def test_assignment_bytes_fields_convert_to_redis_types_sanity(
    bytes_model_with_values,
):
    # Arrange & Act
    bytes_model_with_values.data = b"updated_data"
    bytes_model_with_values.binary_content = b"updated_binary"

    # Assert
    assert isinstance(bytes_model_with_values.data, RedisBytes)
    assert isinstance(bytes_model_with_values.binary_content, RedisBytes)
    assert bytes(bytes_model_with_values.data) == b"updated_data"
    assert bytes(bytes_model_with_values.binary_content) == b"updated_binary"


@pytest.mark.asyncio
async def test_assignment_dict_field_converts_to_redis_type_sanity(
    dict_model_with_values,
):
    # Arrange & Act
    dict_model_with_values.metadata = {"new_key": "new_value", "another": "pair"}

    # Assert
    assert isinstance(dict_model_with_values.metadata, RedisDict)
    assert dict(dict_model_with_values.metadata) == {
        "new_key": "new_value",
        "another": "pair",
    }


@pytest.mark.asyncio
async def test_assignment_mixed_types_all_convert_sanity(mixed_model):
    # Arrange & Act
    mixed_model.str_list = ["string1", "string2"]
    mixed_model.int_list = [1, 2, 3]
    mixed_model.bool_list = [True, False, True]
    mixed_model.bytes_list = [b"bytes1", b"bytes2"]
    mixed_model.str_dict = {"key": "value"}
    mixed_model.int_dict = {"count": 42}
    mixed_model.bool_dict = {"active": True}
    mixed_model.bytes_dict = {"data": b"binary"}

    # Assert - types
    assert isinstance(mixed_model.str_list, RedisList)
    assert isinstance(mixed_model.int_list, RedisList)
    assert isinstance(mixed_model.bool_list, RedisList)
    assert isinstance(mixed_model.bytes_list, RedisList)
    assert isinstance(mixed_model.str_dict, RedisDict)
    assert isinstance(mixed_model.int_dict, RedisDict)
    assert isinstance(mixed_model.bool_dict, RedisDict)
    assert isinstance(mixed_model.bytes_dict, RedisDict)

    # Assert - values
    assert list(mixed_model.str_list) == ["string1", "string2"]
    assert list(mixed_model.int_list) == [1, 2, 3]
    assert list(mixed_model.bool_list) == [True, False, True]
    assert list(mixed_model.bytes_list) == [b"bytes1", b"bytes2"]
    assert dict(mixed_model.str_dict) == {"key": "value"}
    assert dict(mixed_model.int_dict) == {"count": 42}
    assert dict(mixed_model.bool_dict) == {"active": True}
    assert dict(mixed_model.bytes_dict) == {"data": b"binary"}


# Edge cases
@pytest.mark.asyncio
async def test_reassignment_overwrites_correctly_sanity(user_model_with_tags):
    # Arrange
    initial_tags = list(user_model_with_tags.tags)

    # Act
    user_model_with_tags.tags = ["new", "tags", "list"]

    # Assert
    assert isinstance(user_model_with_tags.tags, RedisList)
    assert list(user_model_with_tags.tags) == ["new", "tags", "list"]
    assert list(user_model_with_tags.tags) != initial_tags


@pytest.mark.asyncio
async def test_numeric_type_coercion_edge_case(int_model_with_values):
    # Arrange & Act
    int_model_with_values.count = 42.0  # float should convert to int

    # Assert
    assert isinstance(int_model_with_values.count, RedisInt)
    assert int(int_model_with_values.count) == 42


@pytest.mark.asyncio
async def test_empty_collections_assignment_edge_case(mixed_model):
    # Arrange & Act
    mixed_model.str_list = []
    mixed_model.str_dict = {}

    # Assert
    assert isinstance(mixed_model.str_list, RedisList)
    assert isinstance(mixed_model.str_dict, RedisDict)
    assert list(mixed_model.str_list) == []
    assert dict(mixed_model.str_dict) == {}


@pytest.mark.asyncio
async def test_assignment_preserves_previous_field_conversions_sanity(
    str_model_with_values,
):
    # Arrange
    str_model_with_values.name = "first_update"

    # Act
    str_model_with_values.description = "second_update"

    # Assert - both fields should still be Redis types
    assert isinstance(str_model_with_values.name, RedisStr)
    assert isinstance(str_model_with_values.description, RedisStr)
    assert str(str_model_with_values.name) == "first_update"
    assert str(str_model_with_values.description) == "second_update"


@pytest.mark.asyncio
async def test_assignment_none_to_nullable_field_sanity(none_model_with_values):
    # Arrange & Act
    none_model_with_values.optional_string = None
    none_model_with_values.optional_int = None

    # Assert
    assert none_model_with_values.optional_string is None
    assert none_model_with_values.optional_int is None


@pytest.mark.asyncio
async def test_assignment_none_to_non_nullable_field_validation_error():
    # Arrange & Act
    with pytest.raises(ValidationError):
        StrModel(name=None)


@pytest.mark.asyncio
async def test_assignment_datetime_field_converts_to_redis_datetime_sanity(
    datetime_model_with_values,
):
    # Arrange
    new_datetime = datetime(2024, 6, 15, 14, 30, 0)

    # Act
    datetime_model_with_values.created_at = new_datetime

    # Assert
    assert isinstance(datetime_model_with_values.created_at, RedisDatetime)
    assert datetime_model_with_values.created_at.timestamp() == new_datetime.timestamp()
    assert (
        datetime_model_with_values.created_at._base_model_link
        is datetime_model_with_values
    )


@pytest.mark.asyncio
async def test_assignment_enum_field_type_unchanged_value_changed_sanity(
    task_model_with_values,
):
    # Arrange
    original_type = type(task_model_with_values.status)

    # Act
    task_model_with_values.status = TaskStatus.COMPLETED
    task_model_with_values.priority = Priority.HIGH

    # Assert
    assert type(task_model_with_values.status) == original_type
    assert type(task_model_with_values.priority) == type(Priority.HIGH)
    assert task_model_with_values.status == TaskStatus.COMPLETED
    assert task_model_with_values.priority == Priority.HIGH
    assert task_model_with_values.status.value == "completed"
    assert task_model_with_values.priority.value == "high"


@pytest.mark.asyncio
async def test_assignment_base_model_field_preserves_structure_sanity(
    outer_model_with_values,
):
    # Arrange
    new_inner_model = InnerMostModel(lst=["new_item1", "new_item2"], counter=10)
    new_middle_model = MiddleModel(
        inner_model=new_inner_model,
        tags=["new_tag1", "new_tag2"],
        metadata={"new_key": "new_value"},
    )

    # Act
    outer_model_with_values.middle_model = new_middle_model

    # Assert
    assert isinstance(outer_model_with_values.middle_model, MiddleModel)
    assert isinstance(outer_model_with_values.middle_model.inner_model, InnerMostModel)
    assert outer_model_with_values.middle_model.inner_model.lst == [
        "new_item1",
        "new_item2",
    ]
    assert outer_model_with_values.middle_model.inner_model.counter == 10
    assert outer_model_with_values.middle_model.tags == ["new_tag1", "new_tag2"]
    assert outer_model_with_values.middle_model.metadata == {"new_key": "new_value"}
