import pytest

from tests.models.collection_types import ComprehensiveTestModel


@pytest.mark.asyncio
async def test_pipeline_recovers_from_noscript_error_after_script_flush_sanity():
    # Arrange
    model = ComprehensiveTestModel(
        tags=["a", "b", "c", "d", "e"],
        metadata={"key1": "value1"},
    )
    await model.asave()

    # Act - flush scripts mid-pipeline to simulate Redis restart
    async with model.apipeline() as redis_model:
        # Multiple pipeline operations to verify all are executed
        redis_model.tags.append("f")  # Regular pipeline command (ARRAPPEND)
        redis_model.tags.remove_range(1, 3)  # Uses evalsha (Lua script)
        redis_model.metadata["key2"] = "value2"  # Dict setitem (JSON.SET)

        # Simulate Redis restart by flushing all scripts
        await model.Meta.redis.execute_command("SCRIPT", "FLUSH")

    # Assert - pipeline should have recovered and ALL changes applied
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["a", "d", "e", "f"]
    assert final_model.metadata == {"key1": "value1", "key2": "value2"}
