import asyncio

import pytest

from rapyer.embeddings.adapter import RedisvlEmbeddingAdapter, build_cache_model_label


class _SyncVectorizer:
    """Simulates a local/CPU-bound vectorizer: only sync `embed`/`embed_many`."""

    def __init__(self, max_length=None):
        self.embed_calls = []
        self.embed_many_calls = []
        self.max_length = max_length

    def embed(self, content):
        self.embed_calls.append(content)
        return [0.1, 0.2, 0.3]

    def embed_many(self, contents):
        self.embed_many_calls.append(list(contents))
        return [[0.1, 0.2, 0.3] for _ in contents]


class _AsyncVectorizer:
    """Simulates a real-async-capable vectorizer: real `aembed`/`aembed_many`."""

    def __init__(self):
        self.aembed_calls = []
        self.aembed_many_calls = []

    async def aembed(self, content):
        self.aembed_calls.append(content)
        return [0.4, 0.5, 0.6]

    async def aembed_many(self, contents):
        self.aembed_many_calls.append(list(contents))
        return [[0.4, 0.5, 0.6] for _ in contents]


class _FakeCache:
    """Fake redisvl EmbeddingsCache honoring the aget/aset/amget/amset signatures."""

    def __init__(self):
        self.store = {}
        self.aget_calls = []
        self.aset_calls = []
        self.amget_calls = []
        self.amset_calls = []

    async def aget(self, content, model_name):
        self.aget_calls.append((content, model_name))
        entry = self.store.get((content, model_name))
        return {"embedding": entry} if entry is not None else None

    async def aset(self, content, model_name, embedding, metadata=None):
        self.aset_calls.append((content, model_name))
        self.store[(content, model_name)] = embedding
        return f"{model_name}:{content}"

    async def amget(self, contents, model_name):
        self.amget_calls.append((list(contents), model_name))
        return [
            (
                {"embedding": self.store[(content, model_name)]}
                if (content, model_name) in self.store
                else None
            )
            for content in contents
        ]

    async def amset(self, items):
        self.amset_calls.append(items)
        return [f"{item['model_name']}:{item['content']}" for item in items]


@pytest.mark.asyncio
async def test_aembed_offloads_unrecognized_sync_vectorizer_to_thread_sanity(
    monkeypatch,
):
    # Arrange
    vectorizer = _SyncVectorizer()
    adapter = RedisvlEmbeddingAdapter(vectorizer, dims=3, model_name="local-model")
    to_thread_calls = []
    original_to_thread = asyncio.to_thread

    async def spy_to_thread(func, *args, **kwargs):
        to_thread_calls.append((func, args, kwargs))
        return await original_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", spy_to_thread)

    # Act
    vector = await adapter.aembed("hi")

    # Assert
    assert vector == [0.1, 0.2, 0.3]
    assert len(to_thread_calls) == 1
    assert to_thread_calls[0][0] == vectorizer.embed
    assert vectorizer.embed_calls == ["hi"]


@pytest.mark.asyncio
async def test_aembed_awaits_allowlisted_async_vectorizer_directly_sanity(
    monkeypatch,
):
    # Arrange
    import rapyer.embeddings.adapter as adapter_module

    vectorizer = _AsyncVectorizer()
    monkeypatch.setattr(
        adapter_module,
        "_ASYNC_CAPABLE_VECTORIZER_MODULES",
        frozenset({_AsyncVectorizer.__module__}),
    )
    adapter = RedisvlEmbeddingAdapter(vectorizer, dims=3, model_name="api-model")
    to_thread_calls = []
    monkeypatch.setattr(
        asyncio, "to_thread", lambda *a, **kw: to_thread_calls.append((a, kw))
    )

    # Act
    vector = await adapter.aembed("hi")

    # Assert
    assert vector == [0.4, 0.5, 0.6]
    assert vectorizer.aembed_calls == ["hi"]
    assert to_thread_calls == []


@pytest.mark.asyncio
async def test_aembed_with_no_cache_invokes_vectorizer_every_call_sanity():
    # Arrange
    vectorizer = _SyncVectorizer()
    adapter = RedisvlEmbeddingAdapter(vectorizer, dims=3, model_name="local-model")

    # Act
    await adapter.aembed("same text")
    await adapter.aembed("same text")

    # Assert
    assert vectorizer.embed_calls == ["same text", "same text"]


@pytest.mark.asyncio
async def test_aembed_with_cache_returns_cached_vector_on_second_call_sanity():
    # Arrange
    vectorizer = _SyncVectorizer()
    cache = _FakeCache()
    adapter = RedisvlEmbeddingAdapter(
        vectorizer,
        dims=3,
        model_name="local-model",
        model_version="2",
        cache=cache,
    )
    expected_label = build_cache_model_label("local-model", "2", 3)

    # Act
    first = await adapter.aembed("same text")
    second = await adapter.aembed("same text")

    # Assert
    assert first == second == [0.1, 0.2, 0.3]
    assert vectorizer.embed_calls == ["same text"]
    assert all(model_name == expected_label for _, model_name in cache.aget_calls)
    assert all(model_name == expected_label for _, model_name in cache.aset_calls)


@pytest.mark.asyncio
async def test_aembed_many_only_calls_vectorizer_for_cache_misses_sanity():
    # Arrange
    vectorizer = _SyncVectorizer()
    cache = _FakeCache()
    adapter = RedisvlEmbeddingAdapter(
        vectorizer, dims=3, model_name="local-model", cache=cache
    )
    label = build_cache_model_label("local-model", "1", 3)
    cache.store[("b", label)] = [0.9, 0.9, 0.9]

    # Act
    results = await adapter.aembed_many(["a", "b", "c"])

    # Assert
    assert vectorizer.embed_many_calls == [["a", "c"]]
    assert results == [[0.1, 0.2, 0.3], [0.9, 0.9, 0.9], [0.1, 0.2, 0.3]]


@pytest.mark.asyncio
async def test_aembed_warns_once_on_truncation_but_still_returns_vector_sanity(
    monkeypatch,
):
    # Arrange
    import rapyer.embeddings.adapter as adapter_module

    vectorizer = _SyncVectorizer(max_length=10)
    adapter = RedisvlEmbeddingAdapter(vectorizer, dims=3, model_name="local-model")
    warnings = []
    monkeypatch.setattr(
        adapter_module.logger, "warning", lambda *a, **kw: warnings.append((a, kw))
    )

    # Act
    vector = await adapter.aembed("x" * 50)

    # Assert
    assert vector == [0.1, 0.2, 0.3]
    assert len(warnings) == 1
