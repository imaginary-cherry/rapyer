from rapyer.embeddings import adapter
from rapyer.embeddings.adapter import (
    DefaultEmbeddingAdapter,
    RedisvlEmbeddingAdapter,
    build_cache_model_label,
)
from rapyer.errors import (
    RedisTextEmbeddingNotMaterializedError,
    RedisTextRealRedisRequiredError,
    VectorDimMismatchError,
)


class FakeResolvedAdapter:
    label = "fake@1:3"


def test_redisvl_embedding_adapter_label_matches_cache_model_label_sanity():
    # Arrange
    field_adapter = RedisvlEmbeddingAdapter(
        vectorizer=object(), dims=3, model_name="m", model_version="2"
    )

    # Act
    label = field_adapter.label

    # Assert
    assert label == "m@2:3" == build_cache_model_label("m", "2", 3)


def test_default_embedding_adapter_label_delegates_to_resolved_adapter_sanity(
    monkeypatch,
):
    # Arrange
    monkeypatch.setattr(
        adapter, "_build_packaged_default_adapter", lambda: FakeResolvedAdapter()
    )
    default_adapter = DefaultEmbeddingAdapter()

    # Act
    label = default_adapter.label

    # Assert
    assert label == "fake@1:3"


def test_vector_dim_mismatch_error_carries_context_as_attributes():
    # Arrange & Act
    error = VectorDimMismatchError("body", declared_dim=768, actual_dim=384)

    # Assert
    assert error.field_name == "body"
    assert error.declared_dim == 768
    assert error.actual_dim == 384


def test_redis_text_embedding_not_materialized_error_carries_field_path():
    # Arrange & Act
    error = RedisTextEmbeddingNotMaterializedError("Article:abc123.body")

    # Assert
    assert error.field_path == "Article:abc123.body"


def test_redis_text_real_redis_required_error_carries_model_name():
    # Arrange & Act
    error = RedisTextRealRedisRequiredError("Article")

    # Assert
    assert error.model_name == "Article"
