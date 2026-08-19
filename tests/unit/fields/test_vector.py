from typing import Annotated

import pytest

from rapyer.fields.safe_load import SafeLoadAnnotation
from rapyer.fields.vector import Vector, VectorAnnotation
from rapyer.utils.annotation import get_annotation


def test_vector_returns_vector_annotation_with_given_dim_sanity():
    # Arrange & Act
    result = Vector(dim=768)

    # Assert
    assert isinstance(result, VectorAnnotation)
    assert result.dim == 768
    assert result.metric == "COSINE"
    assert result.algorithm == "FLAT"


def test_vector_accepts_metric_and_algorithm_overrides_sanity():
    # Arrange & Act
    result = Vector(dim=3, metric="L2", algorithm="HNSW")

    # Assert
    assert result.dim == 3
    assert result.metric == "L2"
    assert result.algorithm == "HNSW"


def test_vector_without_dim_raises_type_error():
    # Arrange & Act / Assert
    with pytest.raises(TypeError):
        Vector()


def test_vector_annotation_is_frozen():
    # Arrange
    result = Vector(dim=3)

    # Act / Assert
    with pytest.raises(Exception):
        result.dim = 10


def test_get_annotation_returns_matching_metadata_instance_sanity():
    # Arrange
    annotated_type = Annotated[int, Vector(dim=3)]

    # Act
    result = get_annotation(annotated_type, VectorAnnotation)

    # Assert
    assert isinstance(result, VectorAnnotation)
    assert result.dim == 3


def test_get_annotation_returns_none_when_not_annotated():
    # Arrange & Act
    result = get_annotation(int, VectorAnnotation)

    # Assert
    assert result is None


def test_get_annotation_returns_none_when_annotation_type_not_present():
    # Arrange
    annotated_type = Annotated[int, VectorAnnotation(dim=3)]

    # Act
    result = get_annotation(annotated_type, SafeLoadAnnotation)

    # Assert
    assert result is None
