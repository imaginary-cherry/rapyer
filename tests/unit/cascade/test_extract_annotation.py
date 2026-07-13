from typing import Annotated

from rapyer.cascade import CascadeTTL
from rapyer.fields.key import KeyAnnotation
from rapyer.utils.annotation import extract_annotation

# --- Match ---


def test_matching_metadata_returns_the_exact_instance():
    # Arrange
    spec = CascadeTTL(depth=3)
    field = Annotated[int, spec]

    # Act
    result = extract_annotation(field, CascadeTTL)

    # Assert
    assert result is spec


# --- Wrong type ---


def test_wrong_annotation_type_returns_none():
    # Arrange
    field = Annotated[int, CascadeTTL()]

    # Act
    result = extract_annotation(field, KeyAnnotation)

    # Assert
    assert result is None


# --- Not Annotated at all ---


def test_non_annotated_field_returns_none():
    # Arrange / Act
    result = extract_annotation(int, CascadeTTL)

    # Assert
    assert result is None


# --- Non-matching metadata present ---


def test_non_matching_metadata_returns_none():
    # Arrange
    field = Annotated[int, "some string metadata"]

    # Act
    result = extract_annotation(field, CascadeTTL)

    # Assert
    assert result is None
