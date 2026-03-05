from unittest.mock import AsyncMock

import pytest
from rapyer.errors.base import UnsupportedArgumentValueError
from tests.models.simple_types import StrModel


@pytest.mark.asyncio
async def test_scan_keys_caps_when_single_batch_exceeds_max_results(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    pattern = f"{StrModel.class_key_initials()}:*"
    keys = [f"{StrModel.class_key_initials()}:{i}" for i in range(10)]
    fake_redis_client.scan = AsyncMock(return_value=(0, keys))

    # Act
    result = await StrModel.afind_keys(max_results=3)

    # Assert
    assert len(result) == 3
    fake_redis_client.scan.assert_called_once_with(cursor=0, match=pattern, count=3)


@pytest.mark.asyncio
async def test_scan_keys_caps_when_cumulative_batches_exceed_max_results(
    setup_fake_redis_for_models,
    fake_redis_client,
):
    # Arrange
    batch1 = [f"{StrModel.class_key_initials()}:{i}" for i in range(3)]
    batch2 = [f"{StrModel.class_key_initials()}:{i}" for i in range(3, 8)]
    fake_redis_client.scan = AsyncMock(side_effect=[(1, batch1), (0, batch2)])

    # Act
    result = await StrModel.afind_keys(max_results=5)

    # Assert
    assert len(result) == 5


@pytest.mark.parametrize(["max_results"], [[-1], [-10], [-100]])
@pytest.mark.asyncio
async def test_model_afind_with_negative_max_results_raises_error(max_results):
    # Act & Assert
    with pytest.raises(UnsupportedArgumentValueError):
        await StrModel.afind(max_results=max_results)
