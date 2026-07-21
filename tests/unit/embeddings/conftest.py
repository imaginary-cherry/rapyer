import pytest

from rapyer.embeddings import adapter


@pytest.fixture
def fake_redisvl_import_error(monkeypatch):
    original = adapter._REDISVL_IMPORT_ERROR
    fake_error = ImportError("redisvl not installed")
    monkeypatch.setattr(adapter, "_REDISVL_IMPORT_ERROR", fake_error)
    yield fake_error
    monkeypatch.setattr(adapter, "_REDISVL_IMPORT_ERROR", original)
