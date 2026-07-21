from collections.abc import Sequence

from rapyer.errors import EmbeddingsExtraNotInstalledError, RapyerSerializationError

# Sanctioned exception to "no in-function imports" (Pitfall 9): sole redisvl/numpy import site.
try:
    import numpy as np
    import redisvl  # noqa: F401

    _REDISVL_IMPORT_ERROR: ImportError | None = None
except ImportError as exc:  # pragma: no cover
    np = None
    _REDISVL_IMPORT_ERROR = exc

FLOAT32_ITEM_BYTES = 4


def pack_float32_blob(vector: Sequence[float], dim: int) -> bytes:
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
