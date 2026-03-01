import pytest

import rapyer
from rapyer.fields import RapyerKey


@pytest.mark.asyncio
async def test_module_afind_with_skip_missing_returns_only_existing(
    redis_client, inserted_test_models
):
    # Arrange
    existing_id = inserted_test_models[0].key
    non_existent_id = "IndexTestModel:non_existent_12345"

    # Act
    found_models = await rapyer.afind(existing_id, non_existent_id, skip_missing=True)

    # Assert
    assert len(found_models) == 1
    assert found_models[0] == inserted_test_models[0]
    assert isinstance(found_models[0].key, RapyerKey)
