import pytest

from rapyer.base import AtomicRedisModel
from rapyer.types.integer import RedisInt
from rapyer.types.string import RedisStr
from tests.models.common import Person
from tests.models.inheritance_types import HybridModel


def test_hybrid_model_inherited_fields_converted_to_redis_types_sanity():
    # Act
    model = HybridModel()

    # Assert - fields inherited from SimpleBaseModel are converted to Redis types too.
    assert isinstance(model.username, RedisStr)
    assert isinstance(model.score, RedisInt)
    # Note: bool is pickled, not converted to Redis type
    assert isinstance(model.active, bool)

    # Check that direct AtomicRedisModel fields are also Redis types
    assert isinstance(model.redis_field, RedisStr)
    assert isinstance(model.count, RedisInt)

    # Check that inherited fields have the correct json_path
    assert model.username.json_path == "$.username"
    assert model.score.json_path == "$.score"
    assert model.redis_field.json_path == "$.redis_field"
    assert model.count.json_path == "$.count"

    # Check default values are preserved
    assert model.username == "test_user"
    assert model.score == 100
    assert model.active is True
    assert model.redis_field == "redis_value"
    assert model.count == 42


def test_hybrid_model_custom_values_preserve_redis_types_sanity():
    # Arrange & Act
    model = HybridModel(username="custom_user", score=200, redis_field="custom_redis")

    # Assert - values are set correctly.
    assert model.username == "custom_user"
    assert model.score == 200
    assert model.redis_field == "custom_redis"

    # Check that types are still Redis types after custom initialization
    assert isinstance(model.username, RedisStr)
    assert isinstance(model.score, RedisInt)
    assert isinstance(model.redis_field, RedisStr)

    # Check json_path is still correct
    assert model.username.json_path == "$.username"
    assert model.score.json_path == "$.score"
    assert model.redis_field.json_path == "$.redis_field"

    # Check that all fields are properly accessible in model_dump
    model_dict = model.model_dump()
    assert "username" in model_dict
    assert "score" in model_dict
    assert "active" in model_dict
    assert "redis_field" in model_dict
    assert "count" in model_dict


def test_hybrid_model_inherits_from_person_redis_types_and_json_path_sanity(
    restore_redis_models,
):
    # Arrange
    class PersonRedisModel(AtomicRedisModel, Person):
        redis_status: str = "active"
        priority: int = 1

    # Act
    model = PersonRedisModel(name="John", age=30, email="john@test.com")

    # Assert - values are correct.
    assert model.name == "John"
    assert model.age == 30
    assert model.email == "john@test.com"
    assert model.redis_status == "active"
    assert model.priority == 1

    # Check that inherited Person fields are converted to Redis types
    assert isinstance(model.name, RedisStr)
    assert isinstance(model.age, RedisInt)
    assert isinstance(model.email, RedisStr)

    # Check that direct model fields are also Redis types
    assert isinstance(model.redis_status, RedisStr)
    assert isinstance(model.priority, RedisInt)

    # Check json_path for all fields
    assert model.name.json_path == "$.name"
    assert model.age.json_path == "$.age"
    assert model.email.json_path == "$.email"
    assert model.redis_status.json_path == "$.redis_status"
    assert model.priority.json_path == "$.priority"

    # Check model json_path is correct
    assert model.json_path == "$"


@pytest.mark.parametrize(
    ["test_name", "test_age", "test_email"],
    [
        ["Alice", 25, "alice@example.com"],
        ["Bob", 35, "bob@test.org"],
        ["Charlie", 40, "charlie@domain.net"],
    ],
)
def test_hybrid_model_with_various_values_types_and_json_path_sanity(
    test_name, test_age, test_email, restore_redis_models
):
    # Arrange
    class PersonRedisModel(AtomicRedisModel, Person):
        level: int = 5

    # Act
    model = PersonRedisModel(name=test_name, age=test_age, email=test_email, level=10)

    # Assert - values are correct.
    assert model.name == test_name
    assert model.age == test_age
    assert model.email == test_email
    assert model.level == 10

    # Check that all fields are Redis types
    assert isinstance(model.email, RedisStr)
    assert isinstance(model.age, RedisInt)
    assert isinstance(model.level, RedisInt)
    assert isinstance(model.name, RedisStr)

    # Check json_path for all fields
    assert model.name.json_path == "$.name"
    assert model.age.json_path == "$.age"
    assert model.email.json_path == "$.email"
    assert model.level.json_path == "$.level"
