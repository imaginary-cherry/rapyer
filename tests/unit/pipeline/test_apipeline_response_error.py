from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ResponseError
from tests.models.redis_types import PipelineAllTypesTestModel


@pytest.mark.asyncio
async def test_apipeline_raises_response_error_when_ignore_redis_error_false():
    # Arrange
    model = PipelineAllTypesTestModel(counter=10, name="test")

    mock_json = MagicMock()
    mock_json.set = MagicMock()

    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(side_effect=ResponseError("Test error"))
    mock_pipe.command_stack = []
    mock_pipe.json.return_value = mock_json
    mock_pipe.expire = MagicMock()

    mock_pipeline_context = AsyncMock()
    mock_pipeline_context.__aenter__.return_value = mock_pipe
    mock_pipeline_context.__aexit__.return_value = None

    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipeline_context

    with patch.object(
        PipelineAllTypesTestModel, "aget", new=AsyncMock(return_value=model)
    ):
        original_redis = PipelineAllTypesTestModel.Meta.redis
        PipelineAllTypesTestModel.Meta.redis = mock_redis

        # Act & Assert
        try:
            with pytest.raises(ResponseError):
                async with model.apipeline() as redis_model:
                    redis_model.counter = 99
        finally:
            PipelineAllTypesTestModel.Meta.redis = original_redis
