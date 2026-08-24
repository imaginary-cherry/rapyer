import os

import pytest
from redis.asyncio import Redis as RawRedis

from rapyer import GetOrCreateStatus
from rapyer.types.text import RedisText
from tests.models.special_types import RedisTextModel, VectorAnnotatedTextModel

SF_HASH_FIELDS = {"text", "embedding", "field", "model_label"}


@pytest.mark.asyncio
async def test_redistext_save_excludes_parent_json_and_writes_hash(real_redis_client):
    # Arrange
    model = RedisTextModel(body=RedisText("hello world"))

    # Act
    await model.asave()

    # Assert
    raw_doc = await real_redis_client.json().get(model.key)
    assert "body" not in raw_doc
    assert await real_redis_client.exists(model.body.special_key) == 1
    assert set(await real_redis_client.hkeys(model.body.special_key)) == SF_HASH_FIELDS
    assert await real_redis_client.hget(model.body.special_key, "text") == "hello world"
    assert await real_redis_client.hget(model.body.special_key, "field") == "body"
    # Pitfall A: never decode raw embedding bytes through decode_responses=True.
    strlen = await real_redis_client.execute_command(
        "HSTRLEN", model.body.special_key, "embedding"
    )
    assert strlen == 12


@pytest.mark.asyncio
async def test_redistext_dirty_check_skips_recompute_on_unchanged_resave(
    real_redis_client,
):
    # Arrange
    model = RedisTextModel(body=RedisText("original text"))
    await model.asave()
    vectorizer = model.Meta.vectorizer
    call_count_after_first_save = vectorizer.call_count

    # Act - resave with the identical value: no recompute.
    await model.asave()

    # Assert
    assert vectorizer.call_count == call_count_after_first_save

    # Act - resave with changed text: exactly one more recompute.
    model.body = RedisText("changed text")
    await model.asave()

    # Assert
    assert vectorizer.call_count == call_count_after_first_save + 1
    assert (
        await real_redis_client.hget(model.body.special_key, "text") == "changed text"
    )


@pytest.mark.asyncio
async def test_redistext_get_or_create_writes_hash_atomically_via_lua_path(
    real_redis_client,
):
    # Arrange
    model = RedisTextModel(body=RedisText("created via aget_or_create"))

    # Act
    result = await RedisTextModel.aget_or_create(model)

    # Assert
    assert result.status == GetOrCreateStatus.CREATED
    assert (
        await real_redis_client.hget(model.body.special_key, "text")
        == "created via aget_or_create"
    )
    hash_fields = set(await real_redis_client.hkeys(model.body.special_key))
    assert {"embedding", "field", "model_label"} <= hash_fields


@pytest.mark.asyncio
async def test_vector_annotated_text_model_saves_successfully(real_redis_client):
    # Arrange
    model = VectorAnnotatedTextModel(body=RedisText("vector-annotated text"))

    # Act
    await model.asave()

    # Assert
    raw_doc = await real_redis_client.json().get(model.key)
    assert "body" not in raw_doc
    assert set(await real_redis_client.hkeys(model.body.special_key)) == SF_HASH_FIELDS
    assert (
        await real_redis_client.hget(model.body.special_key, "text")
        == "vector-annotated text"
    )


@pytest.mark.asyncio
async def test_redistext_aduplicate_copies_hash_to_the_duplicates_own_key(
    real_redis_client,
):
    # Arrange
    model = RedisTextModel(body=RedisText("dup me"))
    await model.asave()

    # Act
    duplicate = await model.aduplicate()

    # Assert
    assert duplicate.key != model.key
    assert await real_redis_client.exists(duplicate.body.special_key) == 1
    assert await real_redis_client.hget(duplicate.body.special_key, "text") == "dup me"
    assert await real_redis_client.hget(duplicate.body.special_key, "field") == "body"
    # Nothing in the HASH names the owning model, so the duplicate needs no rewrite --
    # the owner is carried by the key itself, which already differs.
    assert (
        duplicate.body.special_key.rsplit(":", 1)[0].removeprefix("__rapyer_special__:")
        == duplicate.key
    )
    # Source's own HASH is untouched by duplicating it.
    assert await real_redis_client.hget(model.body.special_key, "text") == "dup me"


@pytest.mark.asyncio
async def test_redistext_asave_and_aget_or_create_produce_byte_identical_embeddings(
    real_redis_client,
):
    # Arrange
    model_a = RedisTextModel(body=RedisText("byte identity check"))
    model_b = RedisTextModel(body=RedisText("byte identity check"))

    # Act
    await model_a.asave()
    await RedisTextModel.aget_or_create(model_b)

    db_num = os.getenv("REDIS_DB", "0")
    raw_client = RawRedis.from_url(
        f"redis://localhost:6370/{db_num}", decode_responses=False
    )
    try:
        blob_a = await raw_client.hget(model_a.body.special_key, "embedding")
        blob_b = await raw_client.hget(model_b.body.special_key, "embedding")
    finally:
        await raw_client.aclose()

    # Assert
    assert blob_a == blob_b


@pytest.mark.asyncio
async def test_redistext_aduplicate_of_unsaved_model_creates_no_orphan_hash(
    real_redis_client,
):
    # Arrange - never persisted, so the source SF HASH does not exist
    model = RedisTextModel(body=RedisText("never saved"))
    assert await real_redis_client.exists(model.body.special_key) == 0

    # Act
    duplicates = await model.aduplicate_many(2)

    # Assert - COPY is a no-op here; the parent rewrite must not conjure a stub
    # HASH holding only `parent` (no text/embedding), the way RedisSet and
    # RedisPriorityQueue write nothing at all in the same situation.
    for duplicate in duplicates:
        assert await real_redis_client.exists(duplicate.body.special_key) == 0
