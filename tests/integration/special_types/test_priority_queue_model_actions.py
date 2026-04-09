import pytest
import pytest_asyncio

from rapyer.base import AtomicRedisModel
from rapyer.errors import UpdateAtomicModelError
from rapyer.types.priority_queue import RedisPriorityQueue
from tests.conftest import special_field_test_for
from tests.models.special_types import MixedSpecialModel, PriorityQueueModel


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


@special_field_test_for(AtomicRedisModel.adelete)
@pytest.mark.asyncio
async def test_adelete_model_with_pq_deletes_model_and_pq_keys(
    real_redis_client, saved_pq_model
):
    # Arrange
    model = saved_pq_model
    model_key = model.key
    pq_key = model.tasks.special_key
    assert await real_redis_client.exists(model_key) == 1
    assert await real_redis_client.exists(pq_key) == 1

    # Act
    result = await model.adelete()

    # Assert
    assert result is True
    assert await real_redis_client.exists(model_key) == 0
    assert await real_redis_client.exists(pq_key) == 0


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


# --- ainsert ---


@special_field_test_for(AtomicRedisModel.ainsert)
@pytest.mark.asyncio
async def test_ainsert_multiple_models_with_pq_all_saved(real_redis_client):
    # Arrange
    models = [PriorityQueueModel(name=f"model_{i}") for i in range(3)]

    # Act
    await PriorityQueueModel.ainsert(*models)

    # Assert
    for model in models:
        assert await real_redis_client.exists(model.key) == 1
        await model.tasks.apush("item", 1.0)
        result = await model.tasks.apop()
        assert result == "item"


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


# --- aget ---


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


@special_field_test_for(AtomicRedisModel.aupdate)
@pytest.mark.asyncio
async def test_aupdate_regular_field_on_mixed_model_pq_persists(saved_mixed_model):
    # Arrange
    model = saved_mixed_model

    # Act
    await model.aupdate(name="updated_name", count=99)

    # Assert
    assert model.name == "updated_name"
    assert model.count == 99
    loaded = await MixedSpecialModel.aget(model.key)
    assert loaded.name == "updated_name"
    assert loaded.count == 99
    assert await loaded.tasks.asize() == 2
    assert await loaded.tasks.apop() == "task_a"


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


# --- aduplicate ---


@special_field_test_for(AtomicRedisModel.aduplicate)
@pytest.mark.asyncio
async def test_aduplicate_model_with_pq_duplicate_has_empty_pq(saved_pq_model):
    # Arrange
    model = saved_pq_model

    # Act
    duplicate = await model.aduplicate()

    # Assert
    assert duplicate.pk != model.pk
    assert duplicate.name == model.name
    assert isinstance(duplicate.tasks, RedisPriorityQueue)
    assert await duplicate.tasks.asize() == 0
    assert await model.tasks.asize() == 3


@pytest.mark.asyncio
async def test_aduplicate_pq_operations_on_duplicate_independent(saved_pq_model):
    # Arrange
    model = saved_pq_model

    # Act
    duplicate = await model.aduplicate()
    await duplicate.tasks.apush("new_task", 0.5)

    # Assert
    assert await duplicate.tasks.asize() == 1
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
    assert await duplicate.tasks.asize() == 0
    assert await model.tasks.asize() == 2
