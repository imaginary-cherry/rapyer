import json

import pytest
from pydantic import TypeAdapter

from rapyer.errors import NotResolvedError
from rapyer.types import Reference
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.relational import RelationalFieldType, _resolve_target_model
from tests.models.foreign_key_types import FkAuthor, FkBook

# --- Class-build introspection ---


def test_book_class_classifies_relational_fields():
    # Arrange / Act / Assert
    assert FkBook._relational_field_names == {"author", "publisher"}
    assert FkBook._contain_fk == {"co_authors"}


def test_model_contains_fk_field_reflects_relational_fields():
    # Arrange / Act / Assert
    assert FkBook.contains_fk_field() is True


def test_relational_fields_are_also_redis_link_fields():
    # Arrange / Act
    link_fields = FkBook._redis_link_field_names

    # Assert
    # The metaclass adds every BaseRedisType field to _redis_link_field_names
    # so _base_model_link wiring happens uniformly.
    assert "author" in link_fields


def test_reference_is_relational_field_type():
    # Arrange / Act / Assert
    assert issubclass(Reference, RelationalFieldType)


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


# --- ForeignKey wrapper edge cases ---


@pytest.mark.asyncio
async def test_afetch_unresolved_target_type_raises_type_error():
    # Coverage: ForeignKey.afetch's guard that raises when the target type was
    # never resolved (_relational_target is None).
    # Arrange
    # A bare ForeignKey (not a metaclass per-field subclass) never had its
    # target type resolved, so ``_relational_target`` stays None.
    fk = ForeignKey("FkAuthor:1")

    # Act / Assert
    with pytest.raises(TypeError):
        await fk.afetch()


@pytest.mark.asyncio
async def test_getattr_private_name_raises_attribute_error():
    # Coverage: ForeignKey.__getattr__ early branch for underscore-prefixed
    # names (returns AttributeError instead of delegating).
    # Arrange
    fk = ForeignKey("FkAuthor:1")

    # Act / Assert
    # Underscore-prefixed misses must raise AttributeError, not NotResolvedError,
    # to avoid masking real errors / recursion before _value is set.
    with pytest.raises(AttributeError):
        fk._not_a_real_attribute


def test_foreign_key_is_hashable():
    # Coverage: ForeignKey.__hash__ (so ForeignKeys work in sets / as dict keys).
    # Arrange
    fk_a = ForeignKey("FkAuthor:1")
    fk_b = ForeignKey("FkAuthor:1")
    fk_c = ForeignKey("FkAuthor:2")

    # Act / Assert
    # Equal keys hash equal and collapse in a set; a different key stays distinct.
    assert hash(fk_a) == hash(fk_b)
    assert {fk_a, fk_b, fk_c} == {fk_a, fk_c}


def test_validate_passes_through_existing_foreign_key():
    # Coverage: the validator branch that returns an input value unchanged when
    # it is already a ForeignKey (rather than re-wrapping a key/model).
    # Arrange
    fk = ForeignKey("FkAuthor:99")

    # Act
    # Building a model from an already-built ForeignKey returns it unchanged.
    book = FkBook(title="x", author=fk)

    # Assert
    assert book.author.target_key == "FkAuthor:99"


def test_serializer_handles_none():
    # Coverage: the ForeignKey serializer's None guard. Reachable only by
    # serializing None directly through the type adapter, hence a unit test.
    # Act / Assert
    assert TypeAdapter(ForeignKey).dump_python(None) is None


def test_resolve_target_model_returns_none_for_unnamed_hint():
    # Coverage: _resolve_target_model's branch for a hint with no resolvable
    # name (None) — returns None instead of looking it up.
    # Act / Assert
    assert _resolve_target_model(None) is None


def test_resolve_target_model_returns_none_for_unregistered_non_string_hint():
    # Coverage: _resolve_target_model's final `return None` for a non-string
    # hint whose name matches no registered model.
    # Arrange
    class NotAModel:
        pass

    # Act / Assert
    # A non-string hint whose name matches no registered model yields None
    # (only string hints raise — they are explicit forward references).
    assert _resolve_target_model(NotAModel) is None


def test_resolve_target_model_unregistered_string_raises():
    # Coverage: _resolve_target_model's NameError branch for a string forward
    # reference that names no registered model.
    # Act / Assert
    with pytest.raises(NameError):
        _resolve_target_model("NotARegisteredRapyerModel")
