import asyncio
from typing import ClassVar

import pytest
import pytest_asyncio
from fakeredis import aioredis as fake_aioredis
from pydantic import Field

import rapyer
from rapyer import GetOrCreateStatus
from rapyer.base import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.scripts import register_scripts
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from tests.models.common import UserWithKeyModel
from tests.models.simple_types import StrModel


# --- Sanity: no special-field models ---


@pytest.mark.asyncio
async def test_aget_or_create__creates_when_missing(
    setup_fake_redis_for_models, fake_redis_client
):
    model = StrModel(name="fresh", description="d")

    result = await StrModel.aget_or_create(model)

    assert result.status == GetOrCreateStatus.CREATED
    assert result.value is model
    persisted = await StrModel.aget(model.key)
    assert persisted.name == "fresh"
    assert persisted.description == "d"


@pytest.mark.asyncio
async def test_aget_or_create__returns_existing_when_present(
    setup_fake_redis_for_models, fake_redis_client
):
    existing = UserWithKeyModel(
        user_id="abc", name="existing", email="x@y", age=30
    )
    await existing.asave()

    draft = UserWithKeyModel(
        user_id="abc", name="draft", email="other@y", age=99
    )
    result = await UserWithKeyModel.aget_or_create(draft)

    assert result.status == GetOrCreateStatus.FOUND
    # Must return the pre-existing data, not the draft.
    assert result.value.name == "existing"
    assert result.value.email == "x@y"
    assert result.value.age == 30


@pytest.mark.asyncio
async def test_aget_or_create__concurrent_only_one_creates(
    setup_fake_redis_for_models, fake_redis_client
):
    drafts = [
        UserWithKeyModel(user_id="shared", name=f"d{i}", email="e", age=i)
        for i in range(5)
    ]

    results = await asyncio.gather(
        *(UserWithKeyModel.aget_or_create(d) for d in drafts)
    )

    statuses = [r.status for r in results]
    assert statuses.count(GetOrCreateStatus.CREATED) == 1
    assert statuses.count(GetOrCreateStatus.FOUND) == 4
    # All callers agree on the resulting key's data.
    persisted = await UserWithKeyModel.aget("shared")
    for r in results:
        assert r.value.name == persisted.name
        assert r.value.age == persisted.age


@pytest.mark.asyncio
async def test_aget_or_create__module_level_creates(
    setup_fake_redis_for_models, fake_redis_client
):
    model = StrModel(name="via_module", description="m")

    result = await rapyer.aget_or_create(model)

    assert result.status == GetOrCreateStatus.CREATED
    assert (await StrModel.aget(model.key)).name == "via_module"


@pytest.mark.asyncio
async def test_aget_or_create__module_level_finds(
    setup_fake_redis_for_models, fake_redis_client
):
    existing = UserWithKeyModel(
        user_id="mod_find", name="kept", email="e", age=1
    )
    await existing.asave()

    draft = UserWithKeyModel(
        user_id="mod_find", name="ignored", email="e", age=99
    )
    result = await rapyer.aget_or_create(draft)

    assert result.status == GetOrCreateStatus.FOUND
    assert result.value.name == "kept"
    assert result.value.age == 1


# --- Special-field models (inline fakeredis-bound) ---


class _SetModel(AtomicRedisModel):
    name: str = ""
    tags: RedisSet[str] = Field(default_factory=RedisSet)
    Meta: ClassVar[RedisConfig] = RedisConfig(is_fake_redis=True)


class _QueueModel(AtomicRedisModel):
    label: str = ""
    queue: RedisPriorityQueue[str] = Field(default_factory=RedisPriorityQueue)
    Meta: ClassVar[RedisConfig] = RedisConfig(is_fake_redis=True)


@pytest_asyncio.fixture
async def sf_fake_redis():
    client = fake_aioredis.FakeRedis(decode_responses=True)
    await register_scripts(client, is_fakeredis=True)
    _SetModel.Meta.redis = client
    _QueueModel.Meta.redis = client
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.mark.asyncio
async def test_aget_or_create__creates_with_redis_set(sf_fake_redis):
    model = _SetModel(name="with_set")
    model.tags.update({"a", "b", "c"})

    result = await _SetModel.aget_or_create(model)

    assert result.status == GetOrCreateStatus.CREATED
    # Set members landed in the special key.
    raw_members = await sf_fake_redis.smembers(model.tags.special_key)
    decoded = {m.strip('"') for m in raw_members}
    assert decoded == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_aget_or_create__found_redis_set_preserves_existing_members(
    sf_fake_redis,
):
    existing = _SetModel(name="kept")
    existing.tags.update({"a", "b"})
    await existing.asave()

    draft = _SetModel(name="overwrite-attempt")
    draft._pk = existing.pk
    draft.tags.update({"c", "d"})

    result = await _SetModel.aget_or_create(draft)

    assert result.status == GetOrCreateStatus.FOUND
    assert result.value.name == "kept"
    # Critically: the draft's set is NOT applied; the prior {a, b} stays.
    assert set(result.value.tags) == {"a", "b"}
    raw_members = await sf_fake_redis.smembers(existing.tags.special_key)
    decoded = {m.strip('"') for m in raw_members}
    assert decoded == {"a", "b"}


@pytest.mark.asyncio
async def test_aget_or_create__priority_queue_smoke(sf_fake_redis):
    """Priority queue data is fetched lazily — aget_or_create must not break
    a model that contains one."""
    model = _QueueModel(label="first")

    created = await _QueueModel.aget_or_create(model)
    assert created.status == GetOrCreateStatus.CREATED
    await created.value.queue.apush("task-1", 1.0)

    draft = _QueueModel(label="second")
    draft._pk = model.pk

    found = await _QueueModel.aget_or_create(draft)
    assert found.status == GetOrCreateStatus.FOUND
    assert found.value.label == "first"
    items = await found.value.queue.aitems()
    assert [item.value for item in items] == ["task-1"]


# --- Guard rails ---


@pytest.mark.asyncio
async def test_aget_or_create__rejects_inner_model(
    setup_fake_redis_for_models, fake_redis_client
):
    parent = StrModel(name="p", description="d")
    # Simulate inner-model wiring: attach a base link and a field name.
    inner = StrModel(name="inner", description="d")
    inner._base_model_link = parent
    inner.field_name = ".inner"

    with pytest.raises(RuntimeError, match="top level"):
        await StrModel.aget_or_create(inner)
