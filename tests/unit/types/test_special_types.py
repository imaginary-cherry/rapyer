import pytest
from pydantic import TypeAdapter

from rapyer.errors import RapyerSerializationError, UpdateAtomicModelError
from rapyer.types.base import BaseRedisType
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX, SpecialFieldType
from tests.models.special_types import (
    GenericPriorityQueueModel,
    MixedSpecialModel,
    OverriddenSpecialFieldModel,
    PriorityQueueIntModel,
    PriorityQueueModel,
    SubSubPriorityQueueModel,
)


def test_priority_queue_model_creation_sanity():
    model = PriorityQueueModel(name="test")

    assert isinstance(model.tasks, SpecialFieldType)
    assert isinstance(model.tasks, BaseRedisType)
    assert model.tasks.key == model.key
    assert model.tasks.field_path == ".tasks"
    assert model.tasks.special_key == f"{SPECIAL_FIELD_KEY_PREFIX}:{model.key}:tasks"
    assert model.name == "test"


def test_priority_queue_int_model_creation_sanity():
    model = PriorityQueueIntModel(label="items")

    assert isinstance(model.tasks, SpecialFieldType)
    assert model.tasks.field_path == ".tasks"
    assert model.tasks.special_key == f"{SPECIAL_FIELD_KEY_PREFIX}:{model.key}:tasks"


def test_mixed_special_model_creation_sanity():
    model = MixedSpecialModel(name="mixed", count=42)

    assert isinstance(model.tasks, SpecialFieldType)
    assert model.tasks.special_key == f"{SPECIAL_FIELD_KEY_PREFIX}:{model.key}:tasks"
    assert model.name == "mixed"
    assert model.count == 42


def test_special_field_names_detected():
    assert "tasks" in PriorityQueueModel._special_field_names
    assert "tasks" in MixedSpecialModel._special_field_names
    assert "tasks" in PriorityQueueIntModel._special_field_names
    assert "name" not in PriorityQueueModel._special_field_names
    assert "count" not in MixedSpecialModel._special_field_names


def test_overridden_special_field_not_special():
    # override to non-special type must not leave a stale entry
    assert "tasks" not in OverriddenSpecialFieldModel._special_field_names
    assert "tasks" not in OverriddenSpecialFieldModel._contain_sf
    # _all_keys_for_key no longer crashes on the stale name
    assert OverriddenSpecialFieldModel._all_keys_for_key("X:1") == ["X:1"]


def test_inherited_special_field_still_special():
    # guards against an over-eager fix that prunes inherited fields
    assert "tasks" in SubSubPriorityQueueModel._special_field_names


def test_mixed_redis_dump_excludes_special_fields():
    model = MixedSpecialModel(name="mixed", count=42)
    dump = model.redis_dump()

    assert "name" in dump
    assert "count" in dump
    assert "tasks" not in dump


def test_priority_queue_base_model_link():
    model = PriorityQueueModel(name="test")

    assert model.tasks._base_model_link is model
    assert model.tasks.key == model.key


def test_priority_queue_special_key_format():
    model = PriorityQueueModel(name="test")
    expected_key = f"{SPECIAL_FIELD_KEY_PREFIX}:PriorityQueueModel:{model.pk}:tasks"

    assert model.tasks.special_key == expected_key


def test_priority_queue_clone():
    model = PriorityQueueModel(name="test")
    clone = model.tasks.clone()

    assert isinstance(clone, RedisPriorityQueue)


def test_priority_queue_model_dump_serializes_none():
    model = PriorityQueueModel(name="test")
    dump = model.model_dump()

    assert isinstance(dump["tasks"], RedisPriorityQueue)
    assert dump["name"] == "test"


@pytest.mark.asyncio
async def test_aupdate_raises_error_for_special_field():
    model = MixedSpecialModel(name="mixed", count=42)

    with pytest.raises(UpdateAtomicModelError):
        await model.aupdate(tasks=RedisPriorityQueue())


@pytest.mark.asyncio
async def test_aupdate_raises_error_for_special_field_among_regular_fields():
    model = MixedSpecialModel(name="mixed", count=42)

    with pytest.raises(UpdateAtomicModelError):
        await model.aupdate(name="new_name", tasks=RedisPriorityQueue())


def test_priority_queue_serializer_passes_through_non_collection_value():
    # Coverage: the RedisPriorityQueue serializer's fallback `return v` for a
    # value that is neither a list nor a queue. Only reachable by serializing
    # such a value directly through the type adapter, hence a unit test.
    # The wrap serializer falls back to returning the value unchanged for
    # anything that is neither a list nor a RedisPriorityQueue.
    sentinel = 123
    assert TypeAdapter(RedisPriorityQueue).dump_python(sentinel) == sentinel


# --- Validator / equality edge cases ---


def test_eq_with_non_priority_queue_is_false():
    # TODO(#244): remove once SF field changes are prohibited on an unsaved
#                 model — this exercises an SF field built on a never-persisted model.
    # Coverage: RedisPriorityQueue.__eq__'s branch for a non-queue operand
    # (returns False instead of comparing special keys).
    model = GenericPriorityQueueModel[str]()

    assert (model.tasks == "not-a-queue") is False
    assert model.tasks != "not-a-queue"


def test_init_from_existing_converted_queue_passes_through():
    # TODO(#244): remove once SF field changes are prohibited on an unsaved
    #             model — this exercises an SF field built on a never-persisted model.
    # Coverage: the validator's exact-subclass fast path (isinstance(v, cls) ->
    # return v) when assigning an already-converted queue instance.
    source = GenericPriorityQueueModel[str]()

    # Building a model from an already-converted queue instance returns it
    # unchanged (the exact-subclass fast path, not a re-wrap from a list).
    model = GenericPriorityQueueModel[str](tasks=source.tasks)

    assert isinstance(model.tasks, RedisPriorityQueue)


def test_init_from_list_without_context_raises():
    # Coverage: the validator's ValueError branch — a list is only accepted
    # under the Redis-dump context; a plain assignment must be rejected.
    # A bare list (no Redis dump context) is not a valid queue assignment.
    with pytest.raises(ValueError):
        GenericPriorityQueueModel[str](tasks=[("a", 1.0)])


def test_init_from_invalid_type_raises():
    # Coverage: the validator's RapyerSerializationError branch for an input
    # that is neither a queue, a list, nor a dump-context value.
    with pytest.raises(RapyerSerializationError):
        GenericPriorityQueueModel[str](tasks=123)
