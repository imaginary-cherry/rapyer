from rapyer.cascade import CascadeTTL
from rapyer.cascade.planner import _field_cascade_spec
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBookCollection,
    CascadeBookDirect,
    CascadeBookNested,
    CascadeBookPlain,
    CascadeProfile,
)
from tests.models.foreign_key_types import FkBook

# --- Shape 1: direct FK field ---


def test_direct_fk_field_records_exact_cascade_ttl_instance():
    # Act / Assert
    assert _field_cascade_spec(CascadeBookDirect, "author") == CascadeTTL(enabled=False)


# --- Shape 2: collection-of-FK field ---


def test_collection_fk_field_records_cascade_ttl_on_the_collection_field():
    # Act / Assert
    assert _field_cascade_spec(CascadeBookCollection, "co_authors") == CascadeTTL()


# --- Shape 3: nested submodel with its own cascade-enabled FK field ---


def test_nested_submodel_records_marker_on_the_nested_class_not_the_outer_one():
    # Act / Assert
    assert _field_cascade_spec(CascadeProfile, "mentor") == CascadeTTL()
    assert _field_cascade_spec(CascadeBookNested, "profile") is None


# --- No marker present ---


def test_plain_fk_field_without_cascade_ttl_has_empty_cascade_ttl_fields():
    # Act / Assert
    assert _field_cascade_spec(CascadeBookPlain, "author") is None


def test_plain_fk_field_classification_is_unaffected():
    # Act / Assert
    assert CascadeBookPlain._relational_field_names == {"author"}


def test_cascade_author_leaf_model_has_no_cascade_ttl_fields():
    # Act / Assert
    assert _field_cascade_spec(CascadeAuthor, "name") is None


# --- Regression: existing FK classification unaffected ---


def test_existing_fk_book_classification_remains_byte_identical():
    # Act / Assert
    assert FkBook._relational_field_names == {"author", "publisher"}
    assert FkBook._contain_fk == {"co_authors"}
    assert _field_cascade_spec(FkBook, "author") is None
    assert _field_cascade_spec(FkBook, "publisher") is None
