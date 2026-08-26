from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

import rapyer.base as base_module
from rapyer.base import (
    AtomicRedisModel,
    RedisConfig,
    aget_or_create as module_aget_or_create,
    ainsert as module_ainsert,
)
from rapyer.types.redis_set import RedisSet
from rapyer.types.text import RedisText
from tests.models.simple_types import StrModel


class TwoBodyModel(AtomicRedisModel):
    body1: RedisText = ""
    body2: RedisText = ""

    Meta: ClassVar[RedisConfig] = RedisConfig(redis=MagicMock())


class MixedSFModel(AtomicRedisModel):
    body: RedisText = ""
    tags: RedisSet[str] = RedisSet()

    Meta: ClassVar[RedisConfig] = RedisConfig(redis=MagicMock())


def _mock_vectorizer(vectors):
    vectorizer = MagicMock()
    vectorizer.dims = 3
    vectorizer.aembed_many = AsyncMock(return_value=vectors)
    return vectorizer


@pytest.mark.asyncio
async def test_batches_every_dirty_field_into_one_aembed_many_call():
    model = TwoBodyModel(body1="a", body2="b")
    model.Meta.vectorizer = _mock_vectorizer([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

    await model._aprepare_special_fields()

    # _special_field_names is a set, so assert membership, not literal order.
    model.Meta.vectorizer.aembed_many.assert_awaited_once()
    (call_args,), _ = model.Meta.vectorizer.aembed_many.call_args
    assert sorted(call_args) == ["a", "b"]
    assert model.body1._pending_embedding is not None
    assert model.body2._pending_embedding is not None
    assert model.body1._baseline_text == "a"
    assert model.body2._baseline_text == "b"


@pytest.mark.asyncio
async def test_no_dirty_fields_never_calls_aembed_many():
    model = TwoBodyModel(body1="a", body2="b")
    model.body1._baseline_text = "a"
    model.body2._baseline_text = "b"
    model.Meta.vectorizer = _mock_vectorizer([])

    await model._aprepare_special_fields()

    model.Meta.vectorizer.aembed_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_aprepare_many_dispatched_once_per_lua_type_group(monkeypatch):
    model = MixedSFModel(body="hi")
    model.Meta.vectorizer = _mock_vectorizer([[0.1, 0.2, 0.3]])
    redis_set_prepare = AsyncMock()
    monkeypatch.setattr(RedisSet, "aprepare_many", redis_set_prepare)

    await model._aprepare_special_fields()

    redis_set_prepare.assert_awaited_once_with([model.tags])
    model.Meta.vectorizer.aembed_many.assert_awaited_once_with(["hi"])


@pytest.mark.asyncio
async def test_asave_calls_prepare_before_pipeline_opens(monkeypatch):
    order: list[str] = []

    class SaveOrderModel(AtomicRedisModel):
        name: str = ""

        Meta: ClassVar[RedisConfig] = RedisConfig(redis=MagicMock())

    async def fake_prepare(self):
        order.append("prepare")

    class FakePipeline:
        async def __aenter__(self):
            order.append("pipeline_open")
            return self

        async def __aexit__(self, *exc_info):
            return False

    monkeypatch.setattr(SaveOrderModel, "_aprepare_special_fields", fake_prepare)
    monkeypatch.setattr(base_module, "ensure_pipeline", lambda meta: FakePipeline())
    monkeypatch.setattr(base_module, "get_pipe_json", lambda: MagicMock())

    model = SaveOrderModel(name="x")
    await model.asave()

    assert order == ["prepare", "pipeline_open"]


@pytest.mark.asyncio
async def test_ainsert_classmethod_calls_prepare_before_pipeline_opens(monkeypatch):
    order: list[str] = []

    class InsertOrderModel(AtomicRedisModel):
        name: str = ""

        Meta: ClassVar[RedisConfig] = RedisConfig(redis=MagicMock())

    async def fake_prepare(self):
        order.append("prepare")

    class FakePipeline:
        async def __aenter__(self):
            order.append("pipeline_open")
            return self

        async def __aexit__(self, *exc_info):
            return False

    monkeypatch.setattr(InsertOrderModel, "_aprepare_special_fields", fake_prepare)
    monkeypatch.setattr(base_module, "ensure_pipeline", lambda meta: FakePipeline())
    monkeypatch.setattr(base_module, "get_pipe_json", lambda: MagicMock())

    model = InsertOrderModel(name="x")
    await InsertOrderModel.ainsert(model)

    assert order == ["prepare", "pipeline_open"]


@pytest.mark.asyncio
async def test_module_level_ainsert_calls_prepare_before_pipeline_opens(monkeypatch):
    order: list[str] = []

    class ModuleInsertOrderModel(AtomicRedisModel):
        name: str = ""

        # Own isolated Meta - avoids ttl pollution from AtomicRedisModel.Meta.
        Meta: ClassVar[RedisConfig] = RedisConfig(redis=MagicMock())

    async def fake_prepare(self):
        order.append("prepare")

    class FakePipeline:
        async def __aenter__(self):
            order.append("pipeline_open")
            return self

        async def __aexit__(self, *exc_info):
            return False

    monkeypatch.setattr(AtomicRedisModel, "_aprepare_special_fields", fake_prepare)
    monkeypatch.setattr(base_module, "ensure_pipeline", lambda meta: FakePipeline())
    monkeypatch.setattr(base_module, "get_pipe_json", lambda: MagicMock())

    model = ModuleInsertOrderModel(name="x")
    await module_ainsert(model)

    assert order == ["prepare", "pipeline_open"]


@pytest.mark.asyncio
async def test_aget_or_create_calls_prepare_before_arun_sha(monkeypatch):
    order: list[str] = []

    class GetOrCreateOrderModel(AtomicRedisModel):
        name: str = ""

        Meta: ClassVar[RedisConfig] = RedisConfig(redis=MagicMock())

    async def fake_prepare(self):
        order.append("prepare")

    async def fake_arun_sha(*args, **kwargs):
        order.append("arun_sha")
        return [1, "{}"]

    monkeypatch.setattr(GetOrCreateOrderModel, "_aprepare_special_fields", fake_prepare)
    monkeypatch.setattr(base_module.scripts_registry, "arun_sha", fake_arun_sha)

    model = GetOrCreateOrderModel(name="x")
    await GetOrCreateOrderModel.aget_or_create(model)

    assert order == ["prepare", "arun_sha"]


@pytest.mark.asyncio
async def test_module_level_aget_or_create_delegates_to_classmethod(monkeypatch):
    called = AsyncMock(return_value="sentinel")
    monkeypatch.setattr(StrModel, "aget_or_create", called)

    model = StrModel(name="x")
    result = await module_aget_or_create(model)

    called.assert_awaited_once_with(model)
    assert result == "sentinel"


@pytest.mark.asyncio
async def test_aduplicate_many_does_not_call_prepare(monkeypatch):
    prepare_mock = AsyncMock()
    monkeypatch.setattr(StrModel, "_aprepare_special_fields", prepare_mock)
    monkeypatch.setattr(base_module, "ensure_pipeline", lambda meta: FakeNoopPipeline())

    model = StrModel(name="x")
    await model.aduplicate_many(1)

    prepare_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_aupdate_does_not_call_prepare(monkeypatch):
    prepare_mock = AsyncMock()
    monkeypatch.setattr(StrModel, "_aprepare_special_fields", prepare_mock)
    monkeypatch.setattr(base_module, "ensure_pipeline", lambda meta: FakeNoopPipeline())
    monkeypatch.setattr(base_module, "get_pipe_json", lambda: MagicMock())

    model = StrModel(name="x")
    await model.aupdate(name="y")

    prepare_mock.assert_not_awaited()


class FakeNoopPipeline:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *exc_info):
        return False
