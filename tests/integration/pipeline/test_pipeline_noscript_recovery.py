import pytest

from rapyer.context import _context_pipe
from rapyer.errors import PersistentNoScriptError
from tests.models.collection_types import ComprehensiveTestModel
from tests.models.simple_types import TTL_TEST_SECONDS, TTLRefreshTestModel


@pytest.mark.asyncio
async def test_pipeline_recovers_from_noscript_error_after_script_flush_sanity(
    real_redis_client,
):
    # Arrange
    model = ComprehensiveTestModel(
        tags=["a", "b", "c", "d", "e"],
        metadata={"key1": "value1"},
    )
    await model.asave()
    # Flush AFTER the establishing save, not before: asave()'s auto TTL-refresh
    # runs the cascade script via ensure_pipeline (its own standalone pipe),
    # which does not self-heal NOSCRIPT (see NOSCRIPT-ISSUE.md) -- only the
    # explicit apipeline() below (backed by _apipeline) does.
    await real_redis_client.execute_command("SCRIPT", "FLUSH")

    # Act
    async with model.apipeline() as redis_model:
        redis_model.tags.append("f")
        redis_model.tags.remove_range(1, 3)
        redis_model.metadata["key2"] = "value2"

    # Assert
    final_model = await ComprehensiveTestModel.aget(model.key)
    assert final_model.tags == ["a", "d", "e", "f"]
    assert final_model.metadata == {"key1": "value1", "key2": "value2"}


@pytest.mark.asyncio
async def test_pipeline_recovers_with_all_redis_types_after_script_flush_sanity(
    real_redis_client,
):
    # Arrange
    model = TTLRefreshTestModel(
        name="original",
        age=10,
        score=1.5,
        tags=["a", "b", "c", "d", "e"],
        settings={"setting1": "value1"},
    )
    await model.asave()
    # Flush AFTER the establishing save (see comment in the sibling test above).
    await real_redis_client.execute_command("SCRIPT", "FLUSH")

    # Act
    async with model.apipeline() as redis_model:
        redis_model.age += 5
        redis_model.score += 2.5
        redis_model.tags.append("f")
        redis_model.tags[0] = "new_a"
        redis_model.tags.remove_range(1, 3)
        redis_model.settings["setting2"] = "value2"
        redis_model.settings.update({"setting3": "value3"})

    # Assert
    final_model = await TTLRefreshTestModel.aget(model.key)
    assert final_model.age == 15
    assert final_model.score == 4.0
    assert final_model.tags == ["new_a", "d", "e", "f"]
    assert final_model.settings == {
        "setting1": "value1",
        "setting2": "value2",
        "setting3": "value3",
    }
    ttl = await model.Meta.redis.ttl(model.key)
    assert TTL_TEST_SECONDS - 2 < ttl <= TTL_TEST_SECONDS


@pytest.mark.asyncio
async def test_pipeline_raises_persistent_noscript_error_when_scripts_keep_failing_error(
    real_redis_client,
    disable_noscript_recovery,
):
    # Arrange - save while scripts are loaded, then flush server-side so only
    # the pipeline's remove_range call hits NOSCRIPT
    model = ComprehensiveTestModel(tags=["a", "b", "c"])
    await model.asave()
    await real_redis_client.execute_command("SCRIPT", "FLUSH")

    # Act & Assert
    with pytest.raises(PersistentNoScriptError) as exc_info:
        async with model.apipeline() as redis_model:
            redis_model.tags.remove_range(0, 1)

    assert _context_pipe.get() is None
    assert "server-side" in str(exc_info.value).lower()
