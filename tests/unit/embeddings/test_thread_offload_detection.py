from rapyer.embeddings import adapter
from rapyer.embeddings.adapter import _requires_thread_offload


class FakeUnknownVectorizer:
    pass


class FakeKnownAsyncVectorizer:
    pass


def test_requires_thread_offload_true_for_unrecognized_module_sanity():
    # Act / Assert - unknown/local vectorizers default to safe thread-offload
    assert _requires_thread_offload(FakeUnknownVectorizer()) is True


def test_requires_thread_offload_false_for_allowlisted_module_sanity(monkeypatch):
    # Arrange
    monkeypatch.setattr(
        adapter,
        "_ASYNC_CAPABLE_VECTORIZER_MODULES",
        frozenset({FakeKnownAsyncVectorizer.__module__}),
    )

    # Act / Assert
    assert _requires_thread_offload(FakeKnownAsyncVectorizer()) is False


def test_async_capable_modules_seeded_with_real_redisvl_provider_paths_sanity():
    # Assert - seeded with dotted module paths verified against installed redisvl==0.23.0
    assert (
        "redisvl.utils.vectorize.text.openai"
        in adapter._ASYNC_CAPABLE_VECTORIZER_MODULES
    )
