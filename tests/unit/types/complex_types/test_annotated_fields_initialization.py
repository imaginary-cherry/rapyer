import pytest
from pydantic import ValidationError
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.string import RedisStr
from tests.models.annotated_types import (
    AnnotatedFieldsModel,
    ComplexAnnotatedModel,
    DefaultAnnotatedModel,
    NestedAnnotatedModel,
    SimpleAnnotatedModel,
    ValidationFieldsModel,
)


def test_simple_annotated_model_creation_sanity():
    # Arrange
    name = "test_name"
    count = 42
    items = ["item1", "item2"]

    # Act
    model = SimpleAnnotatedModel(name=name, count=count, items=items)

    # Assert
    assert isinstance(model.name, RedisStr)
    assert isinstance(model.count, RedisInt)
    assert isinstance(model.items, RedisList)
    assert model.name.key == model.key
    assert model.name.field_path == ".name"
    assert str(model.name) == name
    assert int(model.count) == count
    assert len(model.items) == len(items)


@pytest.mark.parametrize(
    "email", ["test@example.com", "user.name+tag@domain.co.uk", "simple@test.org"]
)
def test_annotated_fields_model_email_creation_sanity(email):
    # Arrange
    age = 25
    tags = ["python", "redis"]
    metadata = {"key": "value"}

    # Act
    model = AnnotatedFieldsModel(email=email, age=age, tags=tags, metadata=metadata)

    # Assert
    assert isinstance(model.email, RedisStr)
    assert isinstance(model.age, RedisInt)
    assert isinstance(model.tags, RedisList)
    assert isinstance(model.metadata, RedisDict)
    assert model.email.key == model.key
    assert model.email.field_path == ".email"
    assert str(model.email) == email


@pytest.mark.parametrize("age", [0, 25, 150])
def test_annotated_fields_model_age_validation_sanity(age):
    # Arrange
    email = "test@example.com"
    tags = ["python"]
    metadata = {"key": "value"}

    # Act
    model = AnnotatedFieldsModel(email=email, age=age, tags=tags, metadata=metadata)

    # Assert
    assert isinstance(model.age, RedisInt)
    assert int(model.age) == age
    assert model.age.field_path == ".age"


@pytest.mark.parametrize("invalid_age", [-1, 151, 200])
def test_annotated_fields_model_age_validation_edge_case(invalid_age):
    # Arrange
    email = "test@example.com"
    tags = ["python"]
    metadata = {"key": "value"}

    # Act & Assert
    with pytest.raises(ValidationError):
        AnnotatedFieldsModel(email=email, age=invalid_age, tags=tags, metadata=metadata)


def test_annotated_fields_model_with_no_validation_sanity():
    # Arrange
    email = "any_string_works_now"
    age = 25
    tags = ["python"]
    metadata = {"key": "value"}

    # Act
    model = AnnotatedFieldsModel(email=email, age=age, tags=tags, metadata=metadata)

    # Assert
    assert isinstance(model.email, RedisStr)
    assert isinstance(model.age, RedisInt)
    assert isinstance(model.tags, RedisList)
    assert isinstance(model.metadata, RedisDict)
    assert str(model.email) == email


@pytest.mark.parametrize(
    "tags", [["python"], ["redis", "database"], ["a", "b", "c", "d", "e"]]
)
def test_annotated_fields_model_tags_initialization_sanity(tags):
    # Arrange
    email = "test@example.com"
    age = 25
    metadata = {"key": "value"}

    # Act
    model = AnnotatedFieldsModel(email=email, age=age, tags=tags, metadata=metadata)

    # Assert
    assert isinstance(model.tags, RedisList)
    assert len(model.tags) == len(tags)
    assert model.tags.field_path == ".tags"
    for i, tag in enumerate(tags):
        assert isinstance(model.tags[i], RedisStr)
        assert str(model.tags[i]) == tag


@pytest.mark.parametrize(
    "username,password",
    [("user123", "Password1"), ("test_user", "MyPass123"), ("admin", "SuperSecure8")],
)
def test_validation_fields_model_creation_sanity(username, password):
    # Arrange
    full_name = "Test User"
    roles = ["user"]
    settings = {"theme": 1}

    # Act
    model = ValidationFieldsModel(
        username=username,
        password=password,
        full_name=full_name,
        roles=roles,
        settings=settings,
    )

    # Assert
    assert isinstance(model.username, RedisStr)
    assert isinstance(model.password, RedisStr)
    assert isinstance(model.full_name, RedisStr)
    assert isinstance(model.roles, RedisList)
    assert isinstance(model.settings, RedisDict)
    assert str(model.username) == username
    assert str(model.password) == password
    assert model.username.field_path == ".username"


@pytest.mark.parametrize(
    "invalid_password", ["short", "nodigits", "nouppercase1", "123456"]
)
def test_validation_fields_model_password_validation_edge_case(invalid_password):
    # Arrange
    username = "testuser"
    full_name = "Test User"

    # Act & Assert
    with pytest.raises(ValidationError):
        ValidationFieldsModel(
            username=username, password=invalid_password, full_name=full_name
        )


@pytest.mark.parametrize(
    "invalid_roles",
    [["invalid_role"], ["admin", "unknown"], ["user", "moderator", "bad_role"]],
)
def test_validation_fields_model_roles_validation_edge_case(invalid_roles):
    # Arrange
    username = "testuser"
    password = "Password1"
    full_name = "Test User"

    # Act & Assert
    with pytest.raises(ValidationError):
        ValidationFieldsModel(
            username=username,
            password=password,
            full_name=full_name,
            roles=invalid_roles,
        )


def test_complex_annotated_model_creation_sanity():
    # Arrange
    user_info = ValidationFieldsModel(
        username="testuser", password="Password1", full_name="Test User"
    )
    nested_data = NestedAnnotatedModel(priority=3, status="active", flags=[True, False])
    identifiers = [1, 2, 3]
    config = {"timeout": 30.5, "retries": 3.0}

    # Act
    model = ComplexAnnotatedModel(
        user_info=user_info,
        nested_data=nested_data,
        identifiers=identifiers,
        config=config,
    )

    # Assert
    assert model.user_info._base_model_link == model
    assert model.nested_data._base_model_link == model
    assert isinstance(model.identifiers, RedisList)
    assert isinstance(model.config, RedisDict)
    assert model.identifiers.field_path == ".identifiers"
    assert model.config.field_path == ".config"


def test_default_annotated_model_creation_sanity():
    # Arrange & Act
    model = DefaultAnnotatedModel()

    # Assert
    assert isinstance(model.title, RedisStr)
    assert isinstance(model.count, RedisInt)
    assert isinstance(model.active, bool)
    # NOTE: Fields with default_factory in Field() don't convert to Redis types
    # This is a known limitation with the current implementation
    assert isinstance(model.items, list)
    assert isinstance(model.attributes, dict)

    assert str(model.title) == "Default Title"
    assert int(model.count) == 0
    assert bool(model.active) == True
    assert len(model.items) == 0
    assert len(model.attributes) == 0

    assert model.title.field_path == ".title"
    assert model.count.field_path == ".count"


def test_default_annotated_model_with_values_creation_sanity():
    # Arrange
    title = "Custom Title"
    count = 5
    active = False
    items = ["item1", "item2"]
    attributes = {"attr1": 1, "attr2": 2}

    # Act
    model = DefaultAnnotatedModel(
        title=title, count=count, active=active, items=items, attributes=attributes
    )

    # Assert
    assert str(model.title) == title
    assert int(model.count) == count
    assert bool(model.active) == active
    assert len(model.items) == len(items)
    assert len(model.attributes) == len(attributes)

    for i, item in enumerate(items):
        assert isinstance(model.items[i], RedisStr)
        assert str(model.items[i]) == item
