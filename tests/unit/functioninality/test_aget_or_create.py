import asyncio

import pytest

import rapyer
from rapyer import GetOrCreateStatus
from rapyer.scripts.loader import load_script
from rapyer.scripts.registry import _inject_sf_dispatch
from rapyer.types.special import SpecialFieldType
from tests.models.common import UserWithKeyModel
from tests.models.simple_types import StrModel
from tests.models.special_types import GenericRedisSetModel, PriorityQueueModel


# --- Sanity: no special-field models ---


@pytest.mark.asyncio
async def test_aget_or_create__creates_when_missing(
    setup_fake_redis_for_models, fake_redis_client
):
    # Arrange
    model = StrModel(name="fresh", description="d")

    # Act
    result = await StrModel.aget_or_create(model)

    # Assert
    assert result.status == GetOrCreateStatus.CREATED
    assert result.value is model
    persisted = await StrModel.aget(model.key)
    assert persisted.name == "fresh"
    assert persisted.description == "d"


@pytest.mark.asyncio
async def test_aget_or_create__returns_existing_when_present(
    setup_fake_redis_for_models, fake_redis_client
):
    # Arrange
    existing = UserWithKeyModel(user_id="abc", name="existing", email="x@y", age=30)
    await existing.asave()
    draft = UserWithKeyModel(user_id="abc", name="draft", email="other@y", age=99)

    # Act
    result = await UserWithKeyModel.aget_or_create(draft)

    # Assert
    assert result.status == GetOrCreateStatus.FOUND
    assert result.value.name == "existing"
    assert result.value.email == "x@y"
    assert result.value.age == 30


@pytest.mark.asyncio
async def test_aget_or_create__concurrent_only_one_creates(
    setup_fake_redis_for_models, fake_redis_client
):
    # Arrange
    drafts = [
        UserWithKeyModel(user_id="shared", name=f"d{i}", email="e", age=i)
        for i in range(5)
    ]

    # Act
    results = await asyncio.gather(
        *(UserWithKeyModel.aget_or_create(d) for d in drafts)
    )

    # Assert
    statuses = [r.status for r in results]
    assert statuses.count(GetOrCreateStatus.CREATED) == 1
    assert statuses.count(GetOrCreateStatus.FOUND) == 4
    persisted = await UserWithKeyModel.aget("shared")
    for r in results:
        assert r.value.name == persisted.name
        assert r.value.age == persisted.age


@pytest.mark.asyncio
async def test_aget_or_create__module_level_creates(
    setup_fake_redis_for_models, fake_redis_client
):
    # Arrange
    model = StrModel(name="via_module", description="m")

    # Act
    result = await rapyer.aget_or_create(model)

    # Assert
    assert result.status == GetOrCreateStatus.CREATED
    assert (await StrModel.aget(model.key)).name == "via_module"


@pytest.mark.asyncio
async def test_aget_or_create__module_level_finds(
    setup_fake_redis_for_models, fake_redis_client
):
    # Arrange
    existing = UserWithKeyModel(user_id="mod_find", name="kept", email="e", age=1)
    await existing.asave()
    draft = UserWithKeyModel(user_id="mod_find", name="ignored", email="e", age=99)

    # Act
    result = await rapyer.aget_or_create(draft)

    # Assert
    assert result.status == GetOrCreateStatus.FOUND
    assert result.value.name == "kept"
    assert result.value.age == 1


# --- Special fields ---


@pytest.mark.asyncio
async def test_aget_or_create__creates_with_redis_set(
    setup_fake_redis_for_models, fake_redis_client
):
    # Arrange
    model = GenericRedisSetModel[str](name="with_set")
    model.tags.update({"a", "b", "c"})

    # Act
    result = await GenericRedisSetModel[str].aget_or_create(model)

    # Assert
    assert result.status == GetOrCreateStatus.CREATED
    raw_members = await fake_redis_client.smembers(model.tags.special_key)
    decoded = {m.strip('"') for m in raw_members}
    assert decoded == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_aget_or_create__found_redis_set_preserves_existing_members(
    setup_fake_redis_for_models, fake_redis_client
):
    # Arrange
    existing = GenericRedisSetModel[str](name="kept")
    existing.tags.update({"a", "b"})
    await existing.asave()
    draft = GenericRedisSetModel[str](name="overwrite-attempt")
    draft._pk = existing.pk
    draft.tags.update({"c", "d"})

    # Act
    result = await GenericRedisSetModel[str].aget_or_create(draft)

    # Assert
    assert result.status == GetOrCreateStatus.FOUND
    assert result.value.name == "kept"
    assert set(result.value.tags) == {"a", "b"}
    raw_members = await fake_redis_client.smembers(existing.tags.special_key)
    decoded = {m.strip('"') for m in raw_members}
    assert decoded == {"a", "b"}


@pytest.mark.asyncio
async def test_aget_or_create__priority_queue_smoke(
    setup_fake_redis_for_models, fake_redis_client
):
    # Arrange
    model = PriorityQueueModel(name="first")

    # Act
    created = await PriorityQueueModel.aget_or_create(model)
    await created.value.tasks.apush("task-1", 1.0)
    draft = PriorityQueueModel(name="second")
    draft._pk = model.pk
    found = await PriorityQueueModel.aget_or_create(draft)

    # Assert
    assert created.status == GetOrCreateStatus.CREATED
    assert found.status == GetOrCreateStatus.FOUND
    assert found.value.name == "first"
    items = await found.value.tasks.aitems()
    assert [item.value for item in items] == ["task-1"]


# --- Guard rails ---


@pytest.mark.asyncio
async def test_aget_or_create__rejects_inner_model(
    setup_fake_redis_for_models, fake_redis_client
):
    # Arrange
    parent = StrModel(name="p", description="d")
    inner = StrModel(name="inner", description="d")
    inner._base_model_link = parent
    inner.field_name = ".inner"

    # Act & Assert
    with pytest.raises(RuntimeError, match="top level"):
        await StrModel.aget_or_create(inner)
