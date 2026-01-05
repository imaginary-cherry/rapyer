import pytest

from rapyer import AtomicRedisModel
from rapyer.errors import UnsupportedIndexedFieldError
from tests.models.index_types import (
    UnsupportedIndexModel,
    UnsupportedGenericIndexModel,
    UnsupportedOptionalIndexModel,
)


@pytest.mark.asyncio
async def test_acreate_index_raises_unsupported_filter_field_error_for_unsupported_type_sanity():
    # Act & Assert
    with pytest.raises(UnsupportedIndexedFieldError):
        await UnsupportedIndexModel.acreate_index()


@pytest.mark.asyncio
async def test_acreate_index_raises_unsupported_indexed_field_error_for_unsupported_type_sanity():
    # Act & Assert
    with pytest.raises(UnsupportedIndexedFieldError):
        await UnsupportedIndexModel.acreate_index()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model_class"],
    [
        [UnsupportedGenericIndexModel],
        [UnsupportedOptionalIndexModel],
    ],
)
async def test_acreate_index_raises_unsupported_indexed_field_error_for_generic_annotation_sanity(
    model_class: type[AtomicRedisModel],
):
    # Act & Assert
    with pytest.raises(UnsupportedIndexedFieldError):
        await model_class.acreate_index()
