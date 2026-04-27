import pytest
import pytest_asyncio

from rapyer.base import AtomicRedisModel
from rapyer.errors import UpdateAtomicModelError
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.conftest import special_field_test_for
from tests.models.special_types import (
    MixedSpecialModel,
    PQContainerModel,
    PriorityQueueModel,
    SubSubPriorityQueueModel,
)


@pytest_asyncio.fixture
async def saved_pq_model():
    model = PriorityQueueModel(name="test_model")
    await model.asave()
    await model.tasks.apush("high", 1.0)
    await model.tasks.apush("medium", 2.0)
    await model.tasks.apush("low", 3.0)
    return model


@pytest_asyncio.fixture
async def saved_mixed_model():
    model = MixedSpecialModel(name="mixed_test", count=10)
    await model.asave()
    await model.tasks.apush("task_a", 1.0)
    await model.tasks.apush("task_b", 2.0)
    return model


# --- adelete ---


@pytest.mark.asyncio
async def test_adelete_model_with_empty_pq_deletes_model_key(real_redis_client):
    # Arrange
    model = PriorityQueueModel(name="empty_pq")
    await model.asave()
    assert await real_redis_client.exists(model.key) == 1

    # Act
    result = await model.adelete()

    # Assert
    assert result is True
    assert await real_redis_client.exists(model.key) == 0
    assert await real_redis_client.exists(model.tasks.special_key) == 0


# --- ainsert ---


@pytest.mark.asyncio
async def test_ainsert_mixed_models_regular_fields_and_pq_accessible(real_redis_client):
    # Arrange
    models = [
        MixedSpecialModel(name="mixed_a", count=1),
        MixedSpecialModel(name="mixed_b", count=2),
    ]

    # Act
    await MixedSpecialModel.ainsert(*models)

    # Assert
    for model in models:
        loaded = await MixedSpecialModel.aget(model.key)
        assert loaded.name == model.name
        assert loaded.count == model.count
        await loaded.tasks.apush("test_item", 1.0)
        assert await loaded.tasks.apop() == "test_item"


@pytest.mark.asyncio
async def test_priority_queue_special_key_not_matched_by_model_key_scan(
    real_redis_client,
):
    # Arrange
    model = PriorityQueueModel(name="scan_test")
    await model.asave()
    await model.tasks.apush("job", 1.0)

    # Act
    model_pattern_keys = await real_redis_client.keys(
        f"{PriorityQueueModel.class_key_initials()}:*"
    )
    found_keys = await PriorityQueueModel.afind_keys(max_results=1)

    # Assert
    assert model.key in model_pattern_keys
    assert model.tasks.special_key not in model_pattern_keys
    assert found_keys == [model.key]


# --- aget ---


@special_field_test_for(AtomicRedisModel.aget, RedisPriorityQueue)
@pytest.mark.asyncio
async def test_aget_model_with_pq_data_pq_functional_after_load(saved_pq_model):
    # Arrange
    model = saved_pq_model

    # Act
    loaded = await PriorityQueueModel.aget(model.key)

    # Assert
    assert loaded.name == "test_model"
    assert isinstance(loaded.tasks, RedisPriorityQueue)
    assert await loaded.tasks.asize() == 3
    assert await loaded.tasks.apop() == "high"


@pytest.mark.asyncio
async def test_aget_mixed_model_regular_fields_and_pq_accessible(saved_mixed_model):
    # Arrange
    model = saved_mixed_model

    # Act
    loaded = await MixedSpecialModel.aget(model.key)

    # Assert
    assert loaded.name == "mixed_test"
    assert loaded.count == 10
    assert await loaded.tasks.asize() == 2


# --- aload ---


@special_field_test_for(AtomicRedisModel.aload, RedisPriorityQueue)
@pytest.mark.asyncio
async def test_aload_model_with_pq_reloaded_has_functional_pq(saved_pq_model):
    # Arrange
    model = saved_pq_model

    # Act
    reloaded = await model.aload()

    # Assert
    assert reloaded.name == "test_model"
    assert isinstance(reloaded.tasks, RedisPriorityQueue)
    assert await reloaded.tasks.asize() == 3
    assert await reloaded.tasks.apop() == "high"


@pytest.mark.asyncio
async def test_aload_after_pq_modification_sees_current_state(saved_pq_model):
    # Arrange
    model = saved_pq_model
    await model.tasks.apush("urgent", 0.5)

    # Act
    reloaded = await model.aload()

    # Assert
    assert await reloaded.tasks.asize() == 4
    assert await reloaded.tasks.apop() == "urgent"


# --- afind ---


@special_field_test_for(AtomicRedisModel.afind, RedisPriorityQueue)
@pytest.mark.asyncio
async def test_afind_all_models_with_pq_returned_with_functional_pq(real_redis_client):
    # Arrange
    for i in range(3):
        model = PriorityQueueModel(name=f"find_model_{i}")
        await model.asave()
        await model.tasks.apush(f"item_{i}", float(i))

    # Act
    found = await PriorityQueueModel.afind()

    # Assert
    assert len(found) == 3
    for found_model in found:
        assert isinstance(found_model.tasks, RedisPriorityQueue)
        assert await found_model.tasks.asize() == 1
        assert await found_model.tasks.apeek() is not None


@special_field_test_for(AtomicRedisModel.afind_one, RedisPriorityQueue)
@pytest.mark.asyncio
async def test_afind_one_with_pq_returned_with_functional_pq(real_redis_client):
    # Arrange
    model = PriorityQueueModel(name=f"find_model")
    await model.asave()
    await model.tasks.apush(f"item", 0.0)

    # Act
    found_model = await PriorityQueueModel.afind_one(model.key)

    # Assert
    assert found_model is not None
    assert isinstance(found_model.tasks, RedisPriorityQueue)
    assert await found_model.tasks.asize() == 1
    assert await found_model.tasks.apeek() is not None


@pytest.mark.asyncio
async def test_afind_by_keys_returns_models_with_functional_pq(real_redis_client):
    # Arrange
    model_a = PriorityQueueModel(name="find_a")
    await model_a.asave()
    await model_a.tasks.apush("alpha", 1.0)

    model_b = PriorityQueueModel(name="find_b")
    await model_b.asave()
    await model_b.tasks.apush("beta", 2.0)

    # Act
    found = await PriorityQueueModel.afind(model_a.key, model_b.key)

    # Assert
    assert len(found) == 2
    for found_model in found:
        assert await found_model.tasks.asize() == 1


# --- aupdate ---


@pytest.mark.asyncio
async def test_aupdate_with_pq_field_raises_error(saved_mixed_model):
    # Arrange
    model = saved_mixed_model

    # Act & Assert
    with pytest.raises(UpdateAtomicModelError, match="tasks"):
        await model.aupdate(tasks=RedisPriorityQueue())

    # Assert
    assert await model.tasks.asize() == 2


@pytest.mark.asyncio
async def test_aupdate_regular_and_pq_field_together_raises_error(saved_mixed_model):
    # Arrange
    model = saved_mixed_model

    # Act & Assert
    with pytest.raises(UpdateAtomicModelError):
        await model.aupdate(name="new_name", tasks=RedisPriorityQueue())

    # Assert
    assert model.name == "mixed_test"
    assert await model.tasks.asize() == 2
    loaded_model = await MixedSpecialModel.aget(model.key)
    assert loaded_model.name == "mixed_test"


# --- aduplicate ---


@pytest.mark.asyncio
async def test_aduplicate_pq_operations_on_duplicate_independent(saved_pq_model):
    # Arrange
    model = saved_pq_model

    # Act
    duplicate = await model.aduplicate()
    await duplicate.tasks.apush("new_task", 0.5)

    # Assert
    assert await duplicate.tasks.asize() == 4
    assert await model.tasks.asize() == 3
    assert await model.tasks.apop() == "high"


@pytest.mark.asyncio
async def test_aduplicate_mixed_model_regular_fields_copied_pq_independent(
    saved_mixed_model,
):
    # Arrange
    model = saved_mixed_model

    # Act
    duplicate = await model.aduplicate()

    # Assert
    assert duplicate.name == model.name
    assert duplicate.count == model.count
    assert await duplicate.tasks.asize() == 2
    assert await model.tasks.asize() == 2


# --- aset_ttl ---


@special_field_test_for(AtomicRedisModel.aset_ttl, RedisPriorityQueue)
@pytest.mark.asyncio
async def test_aset_ttl_sets_ttl_on_both_model_and_pq_key(
    real_redis_client, saved_pq_model
):
    # Arrange
    model = saved_pq_model
    model_key = model.key
    pq_key = model.tasks.special_key

    # Act
    await model.aset_ttl(60)

    # Assert
    model_ttl = await real_redis_client.ttl(model_key)
    pq_ttl = await real_redis_client.ttl(pq_key)
    assert 0 < model_ttl <= 60
    assert 0 < pq_ttl <= 60


# --- sub-sub class with PQ in base ---


@pytest.mark.asyncio
async def test_sub_sub_class_pq_has_correct_key_and_actions_work():
    # Arrange
    model = SubSubPriorityQueueModel(name="sub_sub_test", extra="deep")
    await model.asave()

    # Assert - key format
    expected_key = (
        f"{SPECIAL_FIELD_KEY_PREFIX}:SubSubPriorityQueueModel:{model.pk}:tasks"
    )
    assert model.tasks.special_key == expected_key

    # Act - push items with varying priorities
    await model.tasks.apush("low", 3.0)
    await model.tasks.apush("high", 1.0)
    await model.tasks.apush("medium", 2.0)

    # Assert - size
    assert await model.tasks.asize() == 3

    # Assert - peek returns highest priority (lowest score)
    assert await model.tasks.apeek() == "high"

    # Assert - pop order respects priority
    assert await model.tasks.apop() == "high"
    assert await model.tasks.apop() == "medium"
    assert await model.tasks.apop() == "low"
    assert await model.tasks.asize() == 0


# --- contained model with PQ ---


@pytest.mark.asyncio
async def test_contained_model_pq_has_correct_key_and_actions_work():
    # Arrange
    model = PQContainerModel(outer_name="outer_test")
    await model.asave()

    # Assert - key format uses outer model's key
    expected_key = f"{SPECIAL_FIELD_KEY_PREFIX}:PQContainerModel:{model.pk}:tasks"
    assert model.inner_pq.tasks.special_key == expected_key

    # Act - push items via the contained model's PQ
    await model.inner_pq.tasks.apush("low", 3.0)
    await model.inner_pq.tasks.apush("high", 1.0)
    await model.inner_pq.tasks.apush("medium", 2.0)

    # Assert - size
    assert await model.inner_pq.tasks.asize() == 3

    # Assert - peek returns highest priority (lowest score)
    assert await model.inner_pq.tasks.apeek() == "high"

    # Assert - pop order respects priority
    assert await model.inner_pq.tasks.apop() == "high"
    assert await model.inner_pq.tasks.apop() == "medium"
    assert await model.inner_pq.tasks.apop() == "low"
    assert await model.inner_pq.tasks.asize() == 0
