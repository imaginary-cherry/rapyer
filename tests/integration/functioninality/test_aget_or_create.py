import asyncio

import pytest

import rapyer
from rapyer import GetOrCreateStatus
from rapyer.errors import CorruptedModelError
from tests.models.common import UserWithKeyModel
from tests.models.simple_types import IntModel, StrModel
from tests.models.special_types import GenericRedisSetModel, PriorityQueueModel

# --- Sanity: no special-field models ---


@pytest.mark.asyncio
async def test_aget_or_create__creates_when_missing():
    # Arrange
    model = StrModel(name="integration-new", description="real-redis")

    # Act
    result = await StrModel.aget_or_create(model)

    # Assert
    assert result.status == GetOrCreateStatus.CREATED
    assert result.value is model
    persisted = await StrModel.aget(model.key)
    assert persisted.name == "integration-new"
    assert persisted.description == "real-redis"


@pytest.mark.asyncio
async def test_aget_or_create__returns_existing_when_present():
    # Arrange
    existing = UserWithKeyModel(
        user_id="int-existing", name="Alice", email="alice@real.io", age=42
    )
    await existing.asave()
    draft = UserWithKeyModel(
        user_id="int-existing", name="Bob", email="bob@real.io", age=7
    )

    # Act
    result = await UserWithKeyModel.aget_or_create(draft)

    # Assert
    assert result.status == GetOrCreateStatus.FOUND
    assert result.value.name == "Alice"
    assert result.value.email == "alice@real.io"
    assert result.value.age == 42


@pytest.mark.asyncio
async def test_aget_or_create__concurrent_only_one_creates():
    # Arrange
    drafts = [
        UserWithKeyModel(
            user_id="int-race", name=f"contender-{i}", email="r@x.io", age=20 + i
        )
        for i in range(8)
    ]

    # Act
    results = await asyncio.gather(
        *(UserWithKeyModel.aget_or_create(d) for d in drafts)
    )

    # Assert
    statuses = [r.status for r in results]
    assert statuses.count(GetOrCreateStatus.CREATED) == 1
    assert statuses.count(GetOrCreateStatus.FOUND) == 7
    persisted = await UserWithKeyModel.aget("int-race")
    for r in results:
        assert r.value.name == persisted.name
        assert r.value.age == persisted.age


@pytest.mark.asyncio
async def test_aget_or_create__module_level_creates():
    # Arrange
    model = StrModel(name="module-real", description="round-trip")

    # Act
    result = await rapyer.aget_or_create(model)

    # Assert
    assert result.status == GetOrCreateStatus.CREATED
    assert (await StrModel.aget(model.key)).name == "module-real"


@pytest.mark.asyncio
async def test_aget_or_create__module_level_finds():
    # Arrange
    existing = UserWithKeyModel(
        user_id="int-module-found", name="Carla", email="c@real.io", age=55
    )
    await existing.asave()
    draft = UserWithKeyModel(
        user_id="int-module-found", name="Dan", email="d@real.io", age=0
    )

    # Act
    result = await rapyer.aget_or_create(draft)

    # Assert
    assert result.status == GetOrCreateStatus.FOUND
    assert result.value.name == "Carla"
    assert result.value.age == 55


# --- Special fields ---


@pytest.mark.asyncio
async def test_aget_or_create__creates_with_redis_set():
    # Arrange
    model = GenericRedisSetModel[str](name="int-with-set")
    model.tags.update({"red", "green", "blue"})

    # Act
    result = await GenericRedisSetModel[str].aget_or_create(model)

    # Assert
    assert result.status == GetOrCreateStatus.CREATED
    assert await result.value.tags.amembers() == {"red", "green", "blue"}


@pytest.mark.asyncio
async def test_aget_or_create__found_redis_set_preserves_existing_members():
    # Arrange
    existing = GenericRedisSetModel[str](name="int-preserved")
    existing.tags.update({"alpha", "beta"})
    await existing.asave()
    draft = GenericRedisSetModel[str](name="int-overwrite-attempt")
    draft._pk = existing.pk
    draft.tags.update({"gamma", "delta"})

    # Act
    result = await GenericRedisSetModel[str].aget_or_create(draft)

    # Assert
    assert result.status == GetOrCreateStatus.FOUND
    assert result.value.name == "int-preserved"
    assert set(result.value.tags) == {"alpha", "beta"}
    assert await existing.tags.amembers() == {"alpha", "beta"}


@pytest.mark.asyncio
async def test_aget_or_create__priority_queue_smoke():
    # Arrange
    model = PriorityQueueModel(name="int-queue-owner")

    # Act
    created = await PriorityQueueModel.aget_or_create(model)
    await created.value.tasks.apush("ship-it", 0.5)
    await created.value.tasks.apush("review-it", 2.0)
    draft = PriorityQueueModel(name="int-queue-draft")
    draft._pk = model.pk
    found = await PriorityQueueModel.aget_or_create(draft)

    # Assert
    assert created.status == GetOrCreateStatus.CREATED
    assert found.status == GetOrCreateStatus.FOUND
    assert found.value.name == "int-queue-owner"
    items = await found.value.tasks.aitems()
    assert [item.value for item in items] == ["ship-it", "review-it"]


@pytest.mark.asyncio
async def test_aget_or_create__create_co_persists_main_doc_and_sf_state(
    real_redis_client,
):
    # Regression: the create branch runs special-field savers *before* writing
    # the main document, so a successful create must leave both the main key and
    # the SF state present together — never the main doc without its SF members.
    # Arrange
    model = GenericRedisSetModel[str](name="int-co-persist")
    model.tags.update({"x", "y", "z"})

    # Act
    result = await GenericRedisSetModel[str].aget_or_create(model)

    # Assert
    assert result.status == GetOrCreateStatus.CREATED
    assert await real_redis_client.exists(result.value.key) == 1
    assert await result.value.tags.amembers() == {"x", "y", "z"}


@pytest.mark.asyncio
async def test_aget_or_create__create_overrides_stale_server_sf_state(
    real_redis_client,
):
    # Arrange
    model = GenericRedisSetModel[str](name="int-sf-override")
    model.tags.update({"stale-a", "stale-b"})
    await model.asave()
    # Drop only the main JSON doc, leaving the orphaned SF key with stale members.
    assert await real_redis_client.delete(model.key) == 1

    # Act: mutate the same model's SF state locally, then re-create.
    model.tags.clear()
    model.tags.update({"fresh-x", "fresh-y"})
    result = await GenericRedisSetModel[str].aget_or_create(model)

    # Assert: local SF state overrides the stale server members.
    assert result.status == GetOrCreateStatus.CREATED
    assert await real_redis_client.exists(result.value.key) == 1
    assert await result.value.tags.amembers() == {"fresh-x", "fresh-y"}


# --- Guard rails ---


@pytest.mark.asyncio
async def test_aget_or_create__rejects_inner_model():
    # Arrange
    parent = StrModel(name="int-parent", description="d")
    inner = StrModel(name="int-inner", description="d")
    inner._base_model_link = parent
    inner.field_name = ".inner"

    # Act & Assert
    with pytest.raises(RuntimeError, match="top level"):
        await StrModel.aget_or_create(inner)


@pytest.mark.asyncio
async def test_aget_or_create_corrupted_existing_raises_corrupted_model(
    real_redis_client,
):
    # Coverage: aget_or_create's CorruptedModelError branch when the already-
    # existing record can't be validated.
    # Arrange
    model = IntModel()
    await model.asave()
    await real_redis_client.json().set(model.key, "$", {"count": "nope", "score": 1})

    # Act / Assert
    with pytest.raises(CorruptedModelError):
        await IntModel.aget_or_create(model)
