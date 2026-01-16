from unittest.mock import AsyncMock, patch

import pytest

from rapyer.errors import PersistentNoScriptError
from tests.models.collection_types import ComprehensiveTestModel
from tests.models.simple_types import TTLRefreshTestModel


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


@pytest.mark.asyncio
async def test_pipeline_recovers_with_all_redis_types_after_script_flush_sanity():
    # Arrange
    model = TTLRefreshTestModel(
        name="original",
        age=10,
        score=1.5,
        tags=["a", "b", "c", "d", "e"],
        settings={"setting1": "value1"},
    )
    await model.asave()

    # Act - operations on all Redis types then flush scripts
    async with model.apipeline() as redis_model:
        # RedisInt operations
        redis_model.age += 5

        # RedisFloat operations
        redis_model.score += 2.5

        # RedisList operations
        redis_model.tags.append("f")
        redis_model.tags[0] = "new_a"
        redis_model.tags.remove_range(1, 3)  # Lua script (evalsha)

        # RedisDict operations
        redis_model.settings["setting2"] = "value2"
        redis_model.settings.update({"setting3": "value3"})

        # Simulate Redis restart
        await model.Meta.redis.execute_command("SCRIPT", "FLUSH")

    # Assert - all operations on all types should succeed
    final_model = await TTLRefreshTestModel.aget(model.key)
    assert final_model.age == 15
    assert final_model.score == 4.0
    assert final_model.tags == ["new_a", "d", "e", "f"]
    assert final_model.settings == {
        "setting1": "value1",
        "setting2": "value2",
        "setting3": "value3",
    }


@pytest.mark.asyncio
async def test_pipeline_raises_persistent_noscript_error_when_scripts_keep_failing_error():
    # Arrange
    model = ComprehensiveTestModel(tags=["a", "b", "c"])
    await model.asave()
    await model.Meta.redis.execute_command("SCRIPT", "FLUSH")

    # Act & Assert - patch handle_noscript_error to not actually register scripts
    with patch("rapyer.base.handle_noscript_error", new_callable=AsyncMock):
        with pytest.raises(PersistentNoScriptError) as exc_info:
            async with model.apipeline() as redis_model:
                redis_model.tags.remove_range(0, 1)

        assert "server-side" in str(exc_info.value).lower()
