import json
from typing import Optional, get_origin

import pytest
from pydantic import TypeAdapter

from rapyer.base import AtomicRedisModel
from rapyer.errors import NotResolvedError
from rapyer.types import Reference
from rapyer.types.external import FieldTrait
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.relational import RelationalFieldType
from rapyer.utils.pythonic import resolve_generic_args
from tests.models.foreign_key_types import FkAuthor, FkBook

# --- Class-build introspection ---


def test_book_class_classifies_relational_fields():
    # Arrange
    expected_relational = {"author", "publisher"}
    expected_contains_fk = {"co_authors"}

    # Act
    specs = FkBook._field_specs
    is_relational = {
        n
        for n, s in specs.items()
        if s.external and s.external.field_type.traits() & FieldTrait.REFERENCES_ROOT
    }
    contains_fk = {
        n for n, s in specs.items() if s.reaches & FieldTrait.REFERENCES_ROOT
    }

    # Assert
    assert is_relational == expected_relational
    assert contains_fk == expected_contains_fk


def test_model_contains_fk_field_reflects_relational_fields():
    # Arrange / Act / Assert
    assert bool(FkBook.reachable_fields_w_traits() & FieldTrait.REFERENCES_ROOT) is True


def test_relational_fields_are_also_redis_link_fields():
    # Arrange / Act
    link_fields = FkBook.redis_link_fields()

    # Assert - the metaclass adds every BaseRedisType field, so link wiring is uniform.
    assert "author" in link_fields


def test_reference_is_relational_field_type():
    # Arrange / Act / Assert
    assert issubclass(Reference, RelationalFieldType)


def test_foreign_key_fields_are_not_dynamically_subclassed():
    # Arrange - the converter leaves relational types alone, so all FK fields share one class.
    def fk_origin(annotation):
        annotation_origin = get_origin(annotation) or annotation
        if isinstance(annotation_origin, type) and issubclass(
            annotation_origin, ForeignKey
        ):
            return annotation_origin
        # Converted containers carry their args in __orig_bases__, so descend the runtime helper.
        for arg in resolve_generic_args(annotation):
            found = fk_origin(arg)
            if found is not None:
                return found
        return None

    # ACT
    class BareRefHolder(AtomicRedisModel):
        ref: Optional[Reference] = None

    # Assert
    for model, field in [
        (FkBook, "author"),
        (FkBook, "publisher"),
        (FkBook, "co_authors"),
        (BareRefHolder, "ref"),
    ]:
        origin = fk_origin(model.model_fields[field].annotation)
        assert origin is ForeignKey, f"{model.__name__}.{field} is {origin!r}"


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

    # Assert - target fields are reachable directly through the wrapper.
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

    # Act / Assert - wrapper-owned attributes resolve to the wrapper, not the target.
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
    # Arrange - a bare ForeignKey never had its target resolved, so _relational_target is None.
    fk = ForeignKey("FkAuthor:1")

    # Act / Assert
    with pytest.raises(TypeError):
        await fk.afetch()


@pytest.mark.asyncio
async def test_getattr_private_name_raises_attribute_error():
    # Arrange - __getattr__'s underscore branch raises rather than delegating.
    fk = ForeignKey("FkAuthor:1")

    # Act / Assert - underscore misses raise AttributeError so real errors aren't masked.
    with pytest.raises(AttributeError):
        fk._not_a_real_attribute


def test_foreign_key_is_hashable():
    # Arrange - __hash__ is what lets ForeignKeys work in sets and as dict keys.
    fk_a = ForeignKey("FkAuthor:1")
    fk_b = ForeignKey("FkAuthor:1")
    fk_c = ForeignKey("FkAuthor:2")

    # Act / Assert - equal keys hash equal and collapse in a set; a different key stays.
    assert hash(fk_a) == hash(fk_b)
    assert {fk_a, fk_b, fk_c} == {fk_a, fk_c}


def test_validate_passes_through_existing_foreign_key():
    # Arrange - the validator returns an already-built ForeignKey unchanged.
    fk = ForeignKey("FkAuthor:99")

    # Act - building a model from an already-built ForeignKey returns it unchanged.
    book = FkBook(title="x", author=fk)

    # Assert
    assert book.author.target_key == "FkAuthor:99"


def test_serializer_handles_none():
    # Act / Assert - the serializer's None guard is only reachable via the type adapter.
    assert TypeAdapter(ForeignKey).dump_python(None) is None
