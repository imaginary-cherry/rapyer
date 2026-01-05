import pytest

from rapyer.errors import UnsupportedIndexedFieldError
from tests.models.index_types import UnsupportedIndexModel


@pytest.mark.asyncio
async def test_acreate_index_raises_unsupported_filter_field_error_for_unsupported_type_sanity():
    # Act & Assert
    with pytest.raises(UnsupportedIndexedFieldError):
        await UnsupportedIndexModel.acreate_index()
