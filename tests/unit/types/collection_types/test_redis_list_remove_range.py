import logging
from unittest.mock import MagicMock

import pytest

from rapyer.errors import ScriptsNotInitializedError
from rapyer.scripts import _REGISTERED_SCRIPT_SHAS
from rapyer.types.base import _context_var
from tests.models.collection_types import SimpleListModel


@pytest.fixture
def clear_script_state():
    original_shas = _REGISTERED_SCRIPT_SHAS.copy()
    _REGISTERED_SCRIPT_SHAS.clear()
    yield
    _REGISTERED_SCRIPT_SHAS.clear()
    _REGISTERED_SCRIPT_SHAS.update(original_shas)


@pytest.fixture
def model_with_list():
    model = SimpleListModel(items=["a", "b", "c", "d", "e"])
    return model


def test_remove_range_logs_warning_when_no_pipeline_sanity(model_with_list, caplog):
    # Arrange
    with caplog.at_level(logging.WARNING, logger="rapyer"):
        # Act
        model_with_list.items.remove_range(1, 3)

    # Assert
    assert len(caplog.records) == 1
    assert "pipeline" in caplog.records[0].message.lower()
    assert "remove_range" in caplog.records[0].message.lower()


def test_remove_range_does_not_modify_list_when_no_pipeline_sanity(model_with_list):
    # Arrange
    original = list(model_with_list.items)

    # Act
    model_with_list.items.remove_range(1, 3)

    # Assert
    assert list(model_with_list.items) == original


@pytest.mark.asyncio
async def test_remove_range_raises_scripts_not_initialized_error_when_init_rapyer_not_called_error(
    model_with_list, clear_script_state
):
    # Arrange
    mock_pipeline = MagicMock()
    _context_var.set(mock_pipeline)

    # Act & Assert
    try:
        with pytest.raises(ScriptsNotInitializedError) as exc_info:
            async with model_with_list.apipeline():
                model_with_list.items.remove_range(1, 3)

        assert "init_rapyer()" in str(exc_info.value)
    finally:
        _context_var.set(None)
