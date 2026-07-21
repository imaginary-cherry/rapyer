import pytest

from rapyer.embeddings.adapter import _ensure_redisvl_installed
from rapyer.errors import EmbeddingsExtraNotInstalledError


def test_ensure_redisvl_installed_raises_when_missing_sanity(
    fake_redisvl_import_error,
):
    # Act
    with pytest.raises(EmbeddingsExtraNotInstalledError) as exc_info:
        _ensure_redisvl_installed()

    # Assert
    assert exc_info.value.extra_name == "embeddings"
    assert exc_info.value.__cause__ is fake_redisvl_import_error
