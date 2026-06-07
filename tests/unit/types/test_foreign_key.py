import json

import pytest

from rapyer.errors import NotResolvedError
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.relational import RelationalFieldType
from tests.models.foreign_key_types import FkAuthor, FkBook

# --- Class-build introspection ---


def test_book_class_collects_top_level_relational_fields():
    # Arrange / Act
    relational_fields = FkBook._relational_field_names

    # Assert
    # `_relational_field_names` mirrors `_special_field_names`: only direct FK
    # fields are tracked. Generic containers (e.g. `list[ForeignKey[...]]`) are
    # excluded — the same convention as for `list[RedisSet]`.
    assert relational_fields == {"author"}


def test_relational_fields_are_also_redis_link_fields():
    # Arrange / Act
    link_fields = FkBook._redis_link_field_names

    # Assert
    # The metaclass adds every BaseRedisType field to _redis_link_field_names
    # so _base_model_link wiring happens uniformly.
    assert "author" in link_fields


def test_foreign_key_is_relational_field_type():
    # Arrange / Act / Assert
    assert issubclass(ForeignKey, RelationalFieldType)


# --- Pydantic validator: accepts multiple shapes ---


def test_construct_from_instance_resolves_immediately():
    # Arrange
    alice = FkAuthor(name="alice", age=30)

    # Act
    book = FkBook(title="x", author=alice)

    # Assert
    assert book.author.is_resolved is True
    assert book.author.target_key == alice.key
    assert book.author.value is alice


def test_construct_from_key_string_stays_unresolved():
    # Arrange / Act
    book = FkBook(title="x", author="FkAuthor:abc-123")

    # Assert
    assert book.author.is_resolved is False
    assert book.author.target_key == "FkAuthor:abc-123"


def test_construct_from_dbref_dict_stays_unresolved():
    # Arrange / Act
    book = FkBook(title="x", author={"$ref": "FkAuthor", "$id": "abc-123"})

    # Assert
    assert book.author.is_resolved is False
    assert book.author.target_key == "FkAuthor:abc-123"


def test_unresolved_value_raises_not_resolved_error():
    # Arrange
    book = FkBook(title="x", author="FkAuthor:abc-123")

    # Act / Assert
    with pytest.raises(NotResolvedError):
        _ = book.author.value


def test_unknown_input_type_raises():
    # Arrange / Act / Assert
    with pytest.raises(Exception):
        FkBook(title="x", author=12345)


# --- Resolved-state attribute delegation (option 2) ---


def test_resolved_attribute_delegates_to_target():
    # Arrange
    alice = FkAuthor(name="alice", age=30)
    book = FkBook(title="x", author=alice)

    # Act
    name = book.author.name
    age = book.author.age

    # Assert
    # Target fields are reachable directly through the wrapper.
    assert name == "alice"
    assert age == 30


def test_unresolved_attribute_access_raises_not_resolved_error():
    # Arrange
    book = FkBook(title="x", author="FkAuthor:abc-123")

    # Act / Assert
    with pytest.raises(NotResolvedError):
        _ = book.author.name


def test_resolved_missing_attribute_raises_attribute_error():
    # Arrange
    alice = FkAuthor(name="alice")
    book = FkBook(title="x", author=alice)

    # Act / Assert
    with pytest.raises(AttributeError):
        _ = book.author.does_not_exist


def test_wrapper_state_api_not_shadowed_by_delegation():
    # Arrange
    alice = FkAuthor(name="alice")
    book = FkBook(title="x", author=alice)

    # Act / Assert
    # Wrapper-owned attributes resolve to the wrapper, not the target.
    assert book.author.is_resolved is True
    assert book.author.target_key == alice.key
    assert book.author.value is alice


# --- Storage shape ---


def test_redis_dump_emits_target_key_string():
    # Arrange
    alice = FkAuthor(name="alice")
    book = FkBook(title="x", author=alice)

    # Act
    dump = book.redis_dump()

    # Assert
    assert dump["author"] == alice.key


def test_model_dump_json_emits_target_key_string():
    # Arrange
    alice = FkAuthor(name="alice")
    book = FkBook(title="x", author=alice)

    # Act
    payload = json.loads(book.model_dump_json())

    # Assert
    assert payload["author"] == alice.key


def test_list_of_foreign_keys_round_trips_as_array_of_strings():
    # Arrange
    a1 = FkAuthor(name="a1")
    a2 = FkAuthor(name="a2")
    book = FkBook(title="x", author=a1, co_authors=[a1, a2])

    # Act
    dump = book.redis_dump()

    # Assert
    assert dump["co_authors"] == [a1.key, a2.key]


def test_optional_foreign_key_round_trips_as_null():
    # Arrange
    book = FkBook(title="x", author="FkAuthor:1")

    # Act
    dump = book.redis_dump()

    # Assert
    assert book.publisher is None
    assert dump["publisher"] is None
