import pytest

from rapyer.types.base import BaseRedisType
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.special import SpecialFieldType
from tests.models.special_types import (
    PriorityQueueModel,
    PriorityQueueIntModel,
    MixedSpecialModel,
)


def test_priority_queue_model_creation_sanity():
    model = PriorityQueueModel(name="test")

    assert isinstance(model.tasks, SpecialFieldType)
    assert isinstance(model.tasks, BaseRedisType)
    assert model.tasks.key == model.key
    assert model.tasks.field_path == ".tasks"
    assert model.tasks.special_key == f"{model.key}:tasks"
    assert model.name == "test"


def test_priority_queue_int_model_creation_sanity():
    model = PriorityQueueIntModel(label="items")

    assert isinstance(model.queue, SpecialFieldType)
    assert model.queue.field_path == ".queue"
    assert model.queue.special_key == f"{model.key}:queue"


def test_mixed_special_model_creation_sanity():
    model = MixedSpecialModel(name="mixed", count=42)

    assert isinstance(model.tasks, SpecialFieldType)
    assert model.tasks.special_key == f"{model.key}:tasks"
    assert model.name == "mixed"
    assert model.count == 42


def test_special_field_names_detected():
    assert "tasks" in PriorityQueueModel._special_field_names
    assert "tasks" in MixedSpecialModel._special_field_names
    assert "queue" in PriorityQueueIntModel._special_field_names
    assert "name" not in PriorityQueueModel._special_field_names
    assert "count" not in MixedSpecialModel._special_field_names


def test_redis_dump_excludes_special_fields():
    model = PriorityQueueModel(name="test")
    dump = model.redis_dump()

    assert "name" in dump
    assert "tasks" not in dump


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
    expected_key = f"PriorityQueueModel:{model.pk}:tasks"

    assert model.tasks.special_key == expected_key


def test_priority_queue_clone():
    model = PriorityQueueModel(name="test")
    clone = model.tasks.clone()

    assert isinstance(clone, RedisPriorityQueue)


def test_priority_queue_model_dump_serializes_none():
    model = PriorityQueueModel(name="test")
    dump = model.model_dump()

    assert dump["tasks"] is None
    assert dump["name"] == "test"
