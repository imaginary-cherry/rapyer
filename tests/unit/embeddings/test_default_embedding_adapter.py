import pytest

from rapyer.embeddings import adapter
from rapyer.embeddings.adapter import (
    DefaultEmbeddingAdapter,
    default_embedding_adapter,
)
from rapyer.errors import EmbeddingsExtraNotInstalledError


class _DummyVectorizerClass:
    """Stand-in for HFTextVectorizer's minimal (sync, thread-offloaded) call shape."""

    def __init__(self, model):
        self.model = model
        self.embed_calls = []
        self.embed_many_calls = []

    def embed(self, content):
        self.embed_calls.append(content)
        return [0.1, 0.2, 0.3]

    def embed_many(self, contents):
        self.embed_many_calls.append(list(contents))
        return [[0.1, 0.2, 0.3] for _ in contents]


def test_default_embedding_adapter_returns_fresh_instance_each_call_sanity():
    # Act
    first = default_embedding_adapter()
    second = default_embedding_adapter()

    # Assert
    assert isinstance(first, DefaultEmbeddingAdapter)
    assert first is not second


def test_dims_resolves_hf_default_and_caches_resolution_sanity(monkeypatch):
    # Arrange
    monkeypatch.setattr(
        adapter, "_try_import_hf_vectorizer", lambda: _DummyVectorizerClass
    )
    call_count = []
    original = adapter._try_import_hf_vectorizer

    def spy():
        call_count.append(1)
        return original()

    monkeypatch.setattr(adapter, "_try_import_hf_vectorizer", spy)
    default_adapter = DefaultEmbeddingAdapter()

    # Act
    first_dims = default_adapter.dims
    second_dims = default_adapter.dims

    # Assert
    assert first_dims == adapter._HF_DEFAULT_DIMS == 768
    assert second_dims == first_dims
    assert len(call_count) == 1


def test_dims_falls_back_to_openai_when_hf_absent_sanity(monkeypatch):
    # Arrange
    monkeypatch.setattr(adapter, "_try_import_hf_vectorizer", lambda: None)
    monkeypatch.setattr(
        adapter, "_try_import_openai_vectorizer", lambda: _DummyVectorizerClass
    )
    default_adapter = DefaultEmbeddingAdapter()

    # Act
    dims = default_adapter.dims

    # Assert
    assert dims == adapter._OPENAI_DEFAULT_DIMS == 1536


def test_dims_raises_guided_error_when_both_providers_absent_sanity(monkeypatch):
    # Arrange
    monkeypatch.setattr(adapter, "_try_import_hf_vectorizer", lambda: None)
    monkeypatch.setattr(adapter, "_try_import_openai_vectorizer", lambda: None)
    default_adapter = DefaultEmbeddingAdapter()

    # Act / Assert
    with pytest.raises(EmbeddingsExtraNotInstalledError) as exc_info:
        _ = default_adapter.dims
    assert exc_info.value.extra_name == "embeddings-hf"
    assert "rapyer[embeddings-hf]" in str(exc_info.value.args)
    assert "rapyer[embeddings-openai]" in str(exc_info.value.args)


@pytest.mark.asyncio
async def test_aembed_and_aembed_many_delegate_to_resolved_adapter_sanity(
    monkeypatch,
):
    # Arrange
    monkeypatch.setattr(
        adapter, "_try_import_hf_vectorizer", lambda: _DummyVectorizerClass
    )
    default_adapter = DefaultEmbeddingAdapter()

    # Act
    vector = await default_adapter.aembed("hi")
    vectors = await default_adapter.aembed_many(["hi", "there"])

    # Assert
    assert vector == [0.1, 0.2, 0.3]
    assert vectors == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    resolved_vectorizer = default_adapter._resolve()._vectorizer
    assert resolved_vectorizer.embed_calls == ["hi"]
    assert resolved_vectorizer.embed_many_calls == [["hi", "there"]]
