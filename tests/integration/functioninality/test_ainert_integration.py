import pytest
import pytest_asyncio

import rapyer
from tests.models.simple_types import IntModel, StrModel


@pytest_asyncio.fixture
async def transaction_redis(redis_client):
    await redis_client.config_resetstat()
    yield redis_client


@pytest.mark.asyncio
async def test_ainert_multiple_models_single_transaction_sanity(transaction_redis):
    # Arrange
    models = [
        StrModel(name="model1", description="desc1"),
        StrModel(name="model2", description="desc2"),
        StrModel(name="model3", description="desc3"),
        IntModel(count=11),
    ]

    # Act
    await StrModel.ainsert(*models)

    # Assert
    for model in models:
        retrieved_model = await rapyer.aget(model.key)
        assert retrieved_model == model

    info = await transaction_redis.info("commandstats")
    assert info["cmdstat_exec"]["calls"] == 1
