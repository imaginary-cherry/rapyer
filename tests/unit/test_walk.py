from typing import ClassVar, Optional

from pydantic import Field

from rapyer.base import MAX_WALK_DEPTH, AtomicRedisModel, RedisConfig
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.traits import FieldTrait


class WalkPQOnlyChild(AtomicRedisModel):
    tasks: RedisPriorityQueue[str] = Field(
        default_factory=RedisPriorityQueue, exclude=True
    )
    Meta: ClassVar[RedisConfig] = RedisConfig()


class WalkPQOnlyParent(AtomicRedisModel):
    child: WalkPQOnlyChild = None
    Meta: ClassVar[RedisConfig] = RedisConfig()


class WalkSharedLeaf(AtomicRedisModel):
    tasks: RedisPriorityQueue[str] = Field(
        default_factory=RedisPriorityQueue, exclude=True
    )
    Meta: ClassVar[RedisConfig] = RedisConfig()


class WalkTwinParent(AtomicRedisModel):
    left: WalkSharedLeaf = Field(default_factory=WalkSharedLeaf)
    right: WalkSharedLeaf = Field(default_factory=WalkSharedLeaf)
    Meta: ClassVar[RedisConfig] = RedisConfig()


def test_walk_terminates_when_class_already_in_seen():
    # Arrange
    expected_hits = []

    # Act
    hits = list(
        WalkPQOnlyChild.walk(FieldTrait.OWNS_KEYS, _seen=frozenset({WalkPQOnlyChild}))
    )

    # Assert
    assert hits == expected_hits


def test_walk_terminates_past_max_depth():
    # Arrange
    expected_hits = []
    deep_path = tuple(f"level{i}" for i in range(MAX_WALK_DEPTH + 1))

    # Act
    hits = list(WalkPQOnlyChild.walk(FieldTrait.OWNS_KEYS, path=deep_path))

    # Assert
    assert hits == expected_hits


def test_walk_visits_both_siblings_sharing_a_nested_class():
    # Arrange
    expected_paths = {("left", "tasks"), ("right", "tasks")}

    # Act
    paths = {path for _, path in WalkTwinParent.walk(FieldTrait.OWNS_KEYS)}

    # Assert
    assert paths == expected_paths


def test_walk_requires_gate_prunes_subtree_lacking_the_trait():
    # Arrange
    expected_pipeline_load_hits = []
    expected_owns_keys_hit_count = 1

    # Act
    pipeline_load_hits = list(WalkPQOnlyParent.walk(FieldTrait.LOADS_WITH_DOC))
    owns_keys_hits = list(WalkPQOnlyParent.walk(FieldTrait.OWNS_KEYS))

    # Assert
    assert pipeline_load_hits == expected_pipeline_load_hits
    assert len(owns_keys_hits) == expected_owns_keys_hit_count


class WalkOrderedSpecials(AtomicRedisModel):
    child: WalkPQOnlyChild = Field(default_factory=WalkPQOnlyChild)
    tags: RedisSet[str] = Field(default_factory=RedisSet, exclude=True)
    scores: RedisPriorityQueue[str] = Field(
        default_factory=RedisPriorityQueue, exclude=True
    )
    Meta: ClassVar[RedisConfig] = RedisConfig()


def test_iter_special_fields_follows_declaration_order():
    # Arrange
    model = WalkOrderedSpecials()
    expected_paths = [("child", "tasks"), ("tags",), ("scores",)]

    # Act
    paths = [path for _, path in model._iter_special_fields()]

    # Assert
    assert paths == expected_paths


class WalkOptionalSpecialParent(AtomicRedisModel):
    child: Optional[WalkPQOnlyChild] = None
    Meta: ClassVar[RedisConfig] = RedisConfig()


def test_iter_special_fields_skips_an_unset_nested_model():
    # Arrange
    model = WalkOptionalSpecialParent()
    expected_paths = []

    # Act
    paths = [path for _, path in model._iter_special_fields()]

    # Assert
    assert paths == expected_paths
