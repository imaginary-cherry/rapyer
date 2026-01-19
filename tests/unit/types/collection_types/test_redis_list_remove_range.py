import logging

import pytest
from tests.models.collection_types import SimpleListModel


@pytest.fixture
def model_with_list():
    return SimpleListModel(items=["a", "b", "c", "d", "e"])


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
