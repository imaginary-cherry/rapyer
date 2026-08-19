import base64
import json
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from pydantic import TypeAdapter

from rapyer.base import AtomicRedisModel, RedisConfig
from rapyer.errors import (
    RedisTextEmbeddingNotMaterializedError,
    RedisTextRealRedisRequiredError,
)
from rapyer.types.base import REDIS_DUMP_FLAG_NAME, BaseRedisType
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.special import SpecialFieldType
from rapyer.types.text import RedisText


class TextFixtureModel(AtomicRedisModel):
    body: RedisText = ""

    Meta: ClassVar[RedisConfig] = RedisConfig(
        redis=MagicMock(), vectorizer=MagicMock(label="test-model@1:768")
    )


@pytest.fixture(autouse=True)
def _reset_fixture_meta():
    yield
    TextFixtureModel.Meta.is_fake_redis = False


def test_redis_text_plain_string_semantics_and_mro():
    value = RedisText("hello")

    assert value == "hello"
    assert isinstance(value, (str, SpecialFieldType, BaseRedisType))


def test_bare_construction_has_no_baseline():
    value = RedisText("hello")

    assert getattr(value, "_baseline_text", None) is None


def test_model_construction_without_context_is_dirty_by_default():
    model = TextFixtureModel(body="hi")

    assert getattr(model.body, "_baseline_text", None) is None


def test_model_construction_with_redis_dump_context_seeds_clean_baseline():
    instance = TypeAdapter(RedisText).validate_python(
        "hi", context={REDIS_DUMP_FLAG_NAME: True}
    )

    assert instance._baseline_text == "hi"


def test_no_iadd_override_native_str_add():
    result = RedisText("a") + "b"

    assert type(result) is str
    assert result == "ab"


def test_model_dump_serializes_plain_string_regardless_of_context():
    adapter = TypeAdapter(RedisText)

    plain = adapter.dump_python(RedisText("hi"), mode="json")
    redis_ctx = adapter.dump_python(
        RedisText("hi"), mode="json", context={REDIS_DUMP_FLAG_NAME: True}
    )

    assert plain == "hi"
    assert redis_ctx == "hi"


@pytest.mark.asyncio
async def test_asave_special_raises_not_materialized_when_dirty_and_no_pending():
    model = TextFixtureModel(body="dirty")

    with pytest.raises(RedisTextEmbeddingNotMaterializedError):
        await model.body.asave_special()


@pytest.mark.asyncio
async def test_asave_special_clean_omits_embedding():
    model = TextFixtureModel(body="hi")
    model.body._baseline_text = "hi"
    model.Meta.redis.hset = AsyncMock(return_value=None)

    await model.body.asave_special()

    _, kwargs = model.Meta.redis.hset.call_args
    mapping = kwargs["mapping"]
    assert set(mapping.keys()) == {"text", "parent", "field"}


@pytest.mark.asyncio
async def test_asave_special_dirty_includes_embedding_and_clears_pending():
    model = TextFixtureModel(body="hi")
    model.body._pending_embedding = b"\x00\x01\x02\x03"
    model.Meta.redis.hset = AsyncMock(return_value=None)

    await model.body.asave_special()

    _, kwargs = model.Meta.redis.hset.call_args
    mapping = kwargs["mapping"]
    assert mapping["text"] == "hi"
    assert isinstance(mapping["embedding"], bytes)
    assert mapping["embedding"] == b"\x00\x01\x02\x03"
    assert mapping["parent"] == model.key
    assert mapping["field"] == "body"
    assert mapping["model_label"] == "test-model@1:768"
    assert model.body._pending_embedding is None


@pytest.mark.asyncio
async def test_asave_special_raises_real_redis_required_before_touching_client():
    model = TextFixtureModel(body="hi")
    model.Meta.is_fake_redis = True
    model.Meta.redis.hset = AsyncMock(return_value=None)

    with pytest.raises(RedisTextRealRedisRequiredError):
        await model.body.asave_special()

    model.Meta.redis.hset.assert_not_awaited()


@pytest.mark.asyncio
async def test_lua_save_payload_raises_real_redis_required_when_fake():
    model = TextFixtureModel(body="hi")
    model.Meta.is_fake_redis = True

    with pytest.raises(RedisTextRealRedisRequiredError):
        model.body.lua_save_payload()


def test_lua_save_payload_raises_not_materialized_when_no_pending():
    model = TextFixtureModel(body="hi")

    with pytest.raises(RedisTextEmbeddingNotMaterializedError):
        model.body.lua_save_payload()


def test_lua_save_payload_base64_roundtrips():
    model = TextFixtureModel(body="hi")
    model.body._pending_embedding = b"\x00\x01\x02\x03"

    payload = model.body.lua_save_payload()
    decoded = json.loads(payload)

    assert base64.b64decode(decoded["embedding_b64"]) == b"\x00\x01\x02\x03"
    assert decoded["text"] == "hi"
    assert decoded["parent"] == model.key
    assert decoded["field"] == "body"
    assert decoded["model_label"] == "test-model@1:768"


def test_queue_special_loads_in_pipeline_calls_hget_text_only():
    pipe = MagicMock()
    plan = []

    RedisText.queue_special_loads_in_pipeline(
        pipe, "TextFixtureModel:abc", plan, parent_path="", field_name=".body"
    )

    pipe.hget.assert_called_once_with(
        "__rapyer_special__:TextFixtureModel:abc:body", "text"
    )
    assert plan == [["body"]]


def test_clone_returns_new_instance_same_value():
    original = RedisText("x")
    cloned = original.clone()

    assert cloned == "x"
    assert cloned is not original
    assert isinstance(cloned, RedisText)


def test_pending_embed_text_dirty_vs_clean():
    model = TextFixtureModel(body="hi")

    assert model.body.pending_embed_text() == "hi"

    model.body._baseline_text = "hi"

    assert model.body.pending_embed_text() is None


@pytest.mark.asyncio
async def test_aprepare_special_noop_when_no_prepared_vector():
    model = TextFixtureModel(body="hi")

    await model.body.aprepare_special()

    assert getattr(model.body, "_pending_embedding", None) is None
    assert getattr(model.body, "_baseline_text", None) is None


@pytest.mark.asyncio
async def test_aprepare_special_consumes_prepared_vector():
    model = TextFixtureModel(body="hi")
    model.body._prepared_vector = b"\x00\x01\x02\x03"

    await model.body.aprepare_special()

    assert model.body._pending_embedding == b"\x00\x01\x02\x03"
    assert model.body._baseline_text == "hi"
    assert model.body._prepared_vector is None


@pytest.mark.asyncio
async def test_aduplicate_special_copy_then_hset_rewrite():
    model = TextFixtureModel(body="hi")
    model.Meta.redis.copy = AsyncMock(return_value=None)
    model.Meta.redis.hset = AsyncMock(return_value=None)
    tracker = MagicMock()
    tracker.attach_mock(model.Meta.redis.copy, "copy")
    tracker.attach_mock(model.Meta.redis.hset, "hset")

    await model.body.aduplicate_special("target_special_key", "TextFixtureModel:dup")

    assert tracker.mock_calls == [
        call.copy(model.body.special_key, "target_special_key"),
        call.hset(
            "target_special_key",
            mapping={"parent": "TextFixtureModel:dup", "field": "body"},
        ),
    ]


@pytest.mark.asyncio
async def test_redis_set_aduplicate_special_widened_signature_noop_extra_arg():
    field = RedisSet()
    field._base_model_link = TextFixtureModel(body="hi")
    field.field_name = ".tags"
    field.Meta.redis.smembers = AsyncMock(return_value=set())

    await field.aduplicate_special("target_special_key", "ignored_model_key")


@pytest.mark.asyncio
async def test_priority_queue_aduplicate_special_widened_signature_noop_extra_arg():
    field = RedisPriorityQueue()
    field._base_model_link = TextFixtureModel(body="hi")
    field.field_name = ".tasks"
    field.Meta.redis.zrange = AsyncMock(return_value=[])

    await field.aduplicate_special("target_special_key", "ignored_model_key")
