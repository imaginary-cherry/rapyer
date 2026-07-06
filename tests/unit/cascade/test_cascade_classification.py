from rapyer.cascade import CascadeTTL
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
    assert CascadeBookDirect._cascade_ttl_fields == {
        "author": CascadeTTL(enabled=False)
    }


# --- Shape 2: collection-of-FK field ---


def test_collection_fk_field_records_cascade_ttl_on_the_collection_field():
    # Act / Assert
    assert CascadeBookCollection._cascade_ttl_fields == {"co_authors": CascadeTTL()}


# --- Shape 3: nested submodel with its own cascade-enabled FK field ---


def test_nested_submodel_records_marker_on_the_nested_class_not_the_outer_one():
    # Act / Assert
    assert CascadeProfile._cascade_ttl_fields == {"mentor": CascadeTTL()}
    assert CascadeBookNested._cascade_ttl_fields == {}


# --- No marker present ---


def test_plain_fk_field_without_cascade_ttl_has_empty_cascade_ttl_fields():
    # Act / Assert
    assert CascadeBookPlain._cascade_ttl_fields == {}


def test_plain_fk_field_classification_is_unaffected():
    # Act / Assert
    assert CascadeBookPlain._relational_field_names == {"author"}


def test_cascade_author_leaf_model_has_no_cascade_ttl_fields():
    # Act / Assert
    assert CascadeAuthor._cascade_ttl_fields == {}


# --- COMPAT-02 regression: existing FK classification unaffected ---


def test_existing_fk_book_classification_remains_byte_identical():
    # Act / Assert
    assert FkBook._relational_field_names == {"author", "publisher"}
    assert FkBook._contain_fk == {"co_authors"}
    assert FkBook._cascade_ttl_fields == {}
