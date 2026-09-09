from typing import ClassVar

from pydantic import Field

from rapyer.base import MAX_WALK_DEPTH, AtomicRedisModel, RedisConfig
from rapyer.types.external import FieldTrait
from rapyer.types.priority_queue import RedisPriorityQueue


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


def test_walk_accepts_hop_roots_without_changing_owns_keys_result():
    # Arrange / Act
    paths_no_hop = {
        path for _, path in WalkTwinParent.walk(FieldTrait.OWNS_KEYS, hop_roots=False)
    }
    paths_hop = {
        path for _, path in WalkTwinParent.walk(FieldTrait.OWNS_KEYS, hop_roots=True)
    }

    # Assert
    assert paths_no_hop == paths_hop


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
