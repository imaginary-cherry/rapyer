import asyncio
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from rapyer.errors import EmbeddingsExtraNotInstalledError, RapyerSerializationError

if TYPE_CHECKING:
    # Type-hint only - keeps the guarded block the sole runtime redisvl import site.
    from redisvl.extensions.cache.embeddings import EmbeddingsCache

# Sanctioned exception to "no in-function imports" (Pitfall 9): sole redisvl/numpy import site.
try:
    import numpy as np
    import redisvl  # noqa: F401

    _REDISVL_IMPORT_ERROR: ImportError | None = None
except ImportError as exc:  # pragma: no cover
    np = None
    _REDISVL_IMPORT_ERROR = exc

logger = logging.getLogger("rapyer.embeddings")

FLOAT32_ITEM_BYTES = 4

# redisvl==0.23.0 vectorizer modules verified to genuinely override async embed.
_ASYNC_CAPABLE_VECTORIZER_MODULES: frozenset[str] = frozenset(
    {
        "redisvl.utils.vectorize.text.openai",
        "redisvl.utils.vectorize.text.azureopenai",
        "redisvl.utils.vectorize.text.mistral",
        "redisvl.utils.vectorize.text.ollama",
        "redisvl.utils.vectorize.text.voyageai",
    }
)


def _requires_thread_offload(vectorizer: Any) -> bool:
    return type(vectorizer).__module__ not in _ASYNC_CAPABLE_VECTORIZER_MODULES


def pack_float32_blob(vector: Sequence[float], dim: int) -> bytes:
    # Guard first: base install gets the guided error, not a bare AttributeError on None.
    _ensure_redisvl_installed()
    if len(vector) != dim:
        raise RapyerSerializationError(
            f"Vector length {len(vector)} does not match declared dim {dim}"
        )
    blob = np.asarray(vector, dtype=np.float32).tobytes()
    assert len(blob) == dim * FLOAT32_ITEM_BYTES
    return blob


def build_cache_model_label(model_name: str, model_version: str, dim: int) -> str:
    return f"{model_name}@{model_version}:{dim}"


def _ensure_redisvl_installed() -> None:
    if _REDISVL_IMPORT_ERROR is not None:
        raise EmbeddingsExtraNotInstalledError(
            "embeddings",
            'rapyer[embeddings] extra is not installed. Install it with: pip install "rapyer[embeddings]"',
        ) from _REDISVL_IMPORT_ERROR


class RedisvlEmbeddingAdapter:
    """
    Wraps a redisvl vectorizer (+ optional EmbeddingsCache) as an EmbeddingAdapter.

    Normalizes redisvl's uneven async surface (local/CPU-bound vectorizers via
    asyncio.to_thread, real-async API vectorizers awaited directly) and batches
    aembed_many into a single vectorizer call.
    """

    def __init__(
        self,
        vectorizer: Any,
        dims: int,
        model_name: str,
        model_version: str = "1",
        cache: "EmbeddingsCache | None" = None,
    ):
        self._vectorizer = vectorizer
        self._dims = dims
        self._model_name = model_name
        self._model_version = model_version
        self._cache = cache
        self._label = build_cache_model_label(model_name, model_version, dims)

    @property
    def dims(self) -> int:
        return self._dims

    @property
    def label(self) -> str:
        return self._label

    def _warn_if_truncated(self, content: str) -> None:
        # Best-effort signal only, never raises - exact tokenization is provider-specific.
        max_length = getattr(self._vectorizer, "max_length", None)
        if max_length is not None and len(content) > max_length:
            logger.warning(
                "content length %d exceeds vectorizer max_length %d for model %s; "
                "embedding may be silently truncated",
                len(content),
                max_length,
                self._label,
            )

    async def _raw_embed(self, content: str) -> list[float]:
        self._warn_if_truncated(content)
        if _requires_thread_offload(self._vectorizer):
            return await asyncio.to_thread(self._vectorizer.embed, content)
        return await self._vectorizer.aembed(content)

    async def _raw_embed_many(self, contents: list[str]) -> list[list[float]]:
        for content in contents:
            self._warn_if_truncated(content)
        if _requires_thread_offload(self._vectorizer):
            return await asyncio.to_thread(self._vectorizer.embed_many, contents)
        return await self._vectorizer.aembed_many(contents)

    async def aembed(self, content: str) -> list[float]:
        if self._cache is not None:
            hit = await self._cache.aget(content=content, model_name=self._label)
            if hit is not None:
                return list(hit["embedding"])
        vector = await self._raw_embed(content)
        if self._cache is not None:
            await self._cache.aset(
                content=content, model_name=self._label, embedding=vector
            )
        return vector

    async def aembed_many(self, contents: list[str]) -> list[list[float]]:
        if self._cache is None:
            return await self._raw_embed_many(contents)

        cache_hits = await self._cache.amget(contents, self._label)
        results: list[list[float] | None] = [
            list(hit["embedding"]) if hit is not None else None for hit in cache_hits
        ]
        missing_indices = [i for i, result in enumerate(results) if result is None]
        if missing_indices:
            missing_contents = [contents[i] for i in missing_indices]
            missing_vectors = await self._raw_embed_many(missing_contents)
            for i, vector in zip(missing_indices, missing_vectors):
                results[i] = vector
            await self._cache.amset(
                [
                    {
                        "content": contents[i],
                        "model_name": self._label,
                        "embedding": results[i],
                    }
                    for i in missing_indices
                ]
            )
        return results


# D-01/D-02: dim is a schema contract that must never drift with install profile.
_HF_DEFAULT_MODEL = "sentence-transformers/all-mpnet-base-v2"
_HF_DEFAULT_DIMS = 768
_OPENAI_DEFAULT_MODEL = "text-embedding-3-small"
_OPENAI_DEFAULT_DIMS = 1536


def _try_import_hf_vectorizer() -> "type | None":
    try:
        from redisvl.utils.vectorize import HFTextVectorizer
    except ImportError:
        return None
    return HFTextVectorizer


def _try_import_openai_vectorizer() -> "type | None":
    try:
        from redisvl.utils.vectorize import OpenAITextVectorizer
    except ImportError:
        return None
    return OpenAITextVectorizer


def _build_packaged_default_adapter() -> RedisvlEmbeddingAdapter:
    _ensure_redisvl_installed()
    hf_vectorizer_cls = _try_import_hf_vectorizer()
    if hf_vectorizer_cls is not None:
        return RedisvlEmbeddingAdapter(
            hf_vectorizer_cls(model=_HF_DEFAULT_MODEL),
            dims=_HF_DEFAULT_DIMS,
            model_name=_HF_DEFAULT_MODEL,
        )
    openai_vectorizer_cls = _try_import_openai_vectorizer()
    if openai_vectorizer_cls is not None:
        return RedisvlEmbeddingAdapter(
            openai_vectorizer_cls(model=_OPENAI_DEFAULT_MODEL),
            dims=_OPENAI_DEFAULT_DIMS,
            model_name=_OPENAI_DEFAULT_MODEL,
        )
    # Never reads/logs OPENAI_API_KEY here - delegated entirely to OpenAITextVectorizer.
    raise EmbeddingsExtraNotInstalledError(
        "embeddings-hf",
        "No embedding provider installed. Install rapyer[embeddings-hf] (local, "
        "offline) or rapyer[embeddings-openai] (API-based), or configure a custom "
        "vectorizer via Meta.vectorizer / init_rapyer(vectorizer=...).",
    )


class DefaultEmbeddingAdapter:
    """Lazy, zero-config packaged default: HF, else OpenAI, else a guided error."""

    def __init__(self):
        self._resolved: RedisvlEmbeddingAdapter | None = None

    def _resolve(self) -> RedisvlEmbeddingAdapter:
        if self._resolved is None:
            self._resolved = _build_packaged_default_adapter()
        return self._resolved

    @property
    def dims(self) -> int:
        return self._resolve().dims

    @property
    def label(self) -> str:
        return self._resolve().label

    async def aembed(self, content: str) -> list[float]:
        return await self._resolve().aembed(content)

    async def aembed_many(self, contents: list[str]) -> list[list[float]]:
        return await self._resolve().aembed_many(contents)


def default_embedding_adapter() -> DefaultEmbeddingAdapter:
    return DefaultEmbeddingAdapter()
