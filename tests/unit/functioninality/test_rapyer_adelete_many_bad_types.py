import pytest

import rapyer
from rapyer.errors.find import UnsupportArgumentTypeError
from tests.models.index_types import IndexTestModel


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["bad_arg"],
    [
        [1],
        [3.14],
        [None],
        [[1, 2, 3]],
        [{"key": "value"}],
        [True],
        [object()],
    ],
)
async def test_rapyer_adelete_many__bad_type_raises_unsupport_argument_type_error(
    bad_arg,
):
    # Arrange
    # Act & Assert
    with pytest.raises(UnsupportArgumentTypeError):
        await rapyer.adelete_many(bad_arg)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["bad_arg"],
    [
        [1],
        [3.14],
        [None],
        [[1, 2, 3]],
        [{"key": "value"}],
        [True],
        [object()],
    ],
)
async def test_model_adelete_many__bad_type_raises_unsupport_argument_type_error(
    bad_arg,
):
    # Arrange
    # Act & Assert
    with pytest.raises(UnsupportArgumentTypeError):
        await IndexTestModel.adelete_many(bad_arg)
