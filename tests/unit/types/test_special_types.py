import pytest
from pydantic import TypeAdapter

from rapyer.errors import RapyerSerializationError, UpdateAtomicModelError
from rapyer.types.base import BaseRedisType
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX, SpecialFieldType
from tests.models.special_types import (
    GenericPriorityQueueModel,
    ListOfSetsModel,
    MixedSpecialModel,
    OverriddenSpecialFieldModel,
    PQContainerModel,
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


def test_special_fields_detected():
    # Arrange
    expected_special = "tasks"
    expected_plain = ("name", "count")

    # Act / Assert
    assert expected_special in PriorityQueueModel.special_fields()
    assert expected_special in MixedSpecialModel.special_fields()
    assert expected_special in PriorityQueueIntModel.special_fields()
    assert expected_plain[0] not in PriorityQueueModel.special_fields()
    assert expected_plain[1] not in MixedSpecialModel.special_fields()


def test_overridden_special_field_not_special():
    # Arrange - override to a non-special type must not leave a stale entry
    expected_keys = ["X:1"]

    # Act / Assert
    assert "tasks" not in OverriddenSpecialFieldModel.special_fields()
    assert "tasks" not in OverriddenSpecialFieldModel.fields_containing_sf()
    # _all_keys_for_key no longer crashes on the stale name
    assert OverriddenSpecialFieldModel._all_keys_for_key("X:1") == expected_keys


def test_inherited_special_field_still_special():
    # Arrange - guards against an over-eager fix that prunes inherited fields
    expected_special = "tasks"

    # Act / Assert
    assert expected_special in SubSubPriorityQueueModel.special_fields()


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


def test_priority_queue_excluded_from_model_dump():
    model = PriorityQueueModel(name="test")

    python_dump = model.model_dump()
    json_dump = model.model_dump(mode="json")

    assert "tasks" not in python_dump
    assert "tasks" not in json_dump
    assert python_dump["name"] == "test"
    assert json_dump["name"] == "test"


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
    # The wrap serializer returns anything that is neither a list nor a queue unchanged.
    sentinel = 123
    assert TypeAdapter(RedisPriorityQueue).dump_python(sentinel) == sentinel


# --- Validator / equality edge cases ---


def test_eq_with_non_priority_queue_is_false():
    # TODO(#244): remove once SF changes on an unsaved model are prohibited.
    model = GenericPriorityQueueModel[str]()

    assert (model.tasks == "not-a-queue") is False
    assert model.tasks != "not-a-queue"


def test_init_from_existing_converted_queue_passes_through():
    # TODO(#244): remove once SF changes on an unsaved model are prohibited.
    source = GenericPriorityQueueModel[str]()

    # An already-converted queue takes the exact-subclass fast path, not a re-wrap.
    model = GenericPriorityQueueModel[str](tasks=source.tasks)

    assert isinstance(model.tasks, RedisPriorityQueue)


def test_init_from_list_without_context_raises():
    # A bare list (no Redis-dump context) is not a valid queue assignment.
    with pytest.raises(ValueError):
        GenericPriorityQueueModel[str](tasks=[("a", 1.0)])


def test_init_from_invalid_type_raises():
    # Neither a queue, a list, nor a dump-context value hits the serialization error.
    with pytest.raises(RapyerSerializationError):
        GenericPriorityQueueModel[str](tasks=123)


def test_all_keys_for_key_includes_a_direct_special_field_key():
    # Arrange
    key = "PriorityQueueModel:1"
    expected_keys = [key, f"{SPECIAL_FIELD_KEY_PREFIX}:{key}:tasks"]

    # Act
    keys = PriorityQueueModel._all_keys_for_key(key)

    # Assert
    assert keys == expected_keys


def test_all_keys_for_key_includes_a_nested_models_special_key():
    # Arrange
    key = "PQContainerModel:1"
    expected_keys = [key, f"{SPECIAL_FIELD_KEY_PREFIX}:{key}:inner_pq.tasks"]

    # Act
    keys = PQContainerModel._all_keys_for_key(key)

    # Assert
    assert keys == expected_keys


def test_all_keys_for_key_skips_container_of_sf_without_raising():
    # Arrange - a bare list[RedisSet] cannot be descended into; it must not raise.
    expected_keys = ["X:1"]

    # Act
    keys = ListOfSetsModel._all_keys_for_key("X:1")

    # Assert
    assert keys == expected_keys
