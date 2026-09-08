from typing import ClassVar, Optional

from pydantic import Field

from rapyer.base import AtomicRedisModel, FieldSpec, RedisConfig
from rapyer.cascade import CascadeTTL
from rapyer.fields.safe_load import SafeLoad
from rapyer.types.external import Capability
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from tests.models.cascade_types import CascadeBookDirect


class SpecTarget(AtomicRedisModel):
    name: str = ""


class SpecChild(AtomicRedisModel):
    tags: RedisSet[str] = None


class SpecParent(AtomicRedisModel):
    plain: str = ""
    ref: Optional[ForeignKey[SpecTarget]] = None
    refs: RedisSet[ForeignKey[SpecTarget]] = None
    child: SpecChild = None
    safe: SafeLoad[str] = ""
    Meta: ClassVar[RedisConfig] = RedisConfig()


class PQOnlyChild(AtomicRedisModel):
    tasks: RedisPriorityQueue[str] = Field(
        default_factory=RedisPriorityQueue, exclude=True
    )
    Meta: ClassVar[RedisConfig] = RedisConfig()


class PQOnlyParent(AtomicRedisModel):
    child: PQOnlyChild = None
    Meta: ClassVar[RedisConfig] = RedisConfig()


def test_derived_views_match_their_axis_on_the_specs():
    # Arrange
    specs = SpecParent._field_specs
    expected_special = {n for n, s in specs.items() if s.is_special}
    expected_links = frozenset(n for n, s in specs.items() if s.is_redis_link)
    expected_contains_sf = frozenset(n for n, s in specs.items() if s.contains_sf)

    # Act / Assert
    assert set(SpecParent.special_fields()) == expected_special
    assert SpecParent.redis_link_fields() == expected_links
    assert SpecParent.fields_containing_sf() == expected_contains_sf


def test_redis_link_fields_is_a_strict_superset():
    # Arrange - `plain`/`safe` convert to RedisStr, so they're links on no other axis.
    expected_links = {"plain", "refs", "child", "safe"}

    # Act / Assert
    assert SpecParent.redis_link_fields() == expected_links
    assert "plain" not in SpecParent.special_fields()


def test_each_class_caches_its_own_derived_view():
    # Arrange
    class SpecSubclass(SpecParent):
        child: str = ""
        Meta: ClassVar[RedisConfig] = RedisConfig()

    # Act / Assert
    assert "child" in SpecParent.fields_containing_sf()
    assert "child" not in SpecSubclass.fields_containing_sf()


def test_a_field_can_sit_on_several_axes_at_once():
    # Arrange - RedisSet[ForeignKey[...]] is special AND contains_fk AND a link.
    expected_axes = (True, True, True, False)

    # Act
    spec = SpecParent._field_specs["refs"]

    # Assert
    axes = (spec.is_special, spec.contains_fk, spec.is_redis_link, spec.is_relational)
    assert axes == expected_axes


def test_optional_nested_model_is_not_seen_as_containing_a_special_field():
    # A1, pinned deliberately: FK axes strip Optional first, containment axes don't.
    class OptionalChildParent(AtomicRedisModel):
        child: Optional[SpecChild] = None
        Meta: ClassVar[RedisConfig] = RedisConfig()

    # Act / Assert
    assert "child" not in OptionalChildParent._field_specs
    assert OptionalChildParent.fields_containing_sf() == frozenset()


def test_the_two_containment_axes_can_hold_at_once():
    # Arrange - a nested model owning both an SF and an FK puts the parent's field
    # on both containment axes, so they cannot collapse into one flag. No shipped
    # fixture nests such a class, which is why nothing else covers this.
    class BothInner(AtomicRedisModel):
        tags: RedisSet[str] = None
        ref: ForeignKey[SpecTarget] = None
        Meta: ClassVar[RedisConfig] = RedisConfig()

    class BothOuter(AtomicRedisModel):
        child: BothInner = None
        Meta: ClassVar[RedisConfig] = RedisConfig()

    # Act
    spec = BothOuter._field_specs["child"]

    # Assert
    assert spec.contains_sf is True
    assert spec.contains_fk is True


def test_relational_and_contains_fk_are_mutually_exclusive():
    # Arrange - a ForeignKey itself is relational; it does not also "contain" one.
    expected_relational, expected_contains_fk = True, False

    # Act
    spec = SpecParent._field_specs["ref"]

    # Assert
    assert spec.is_relational is expected_relational
    assert spec.contains_fk is expected_contains_fk


def test_an_unclassified_spec_is_not_kept():
    # Arrange
    plain = FieldSpec(name="x", field_type=str)
    classified = FieldSpec(name="x", field_type=str, reaches=Capability.OWNS_KEYS)

    # Act / Assert
    assert plain.is_classified() is False
    assert classified.is_classified() is True


def test_reaches_carries_per_bit_precision_for_a_pq_only_subtree():
    # Arrange - a subtree holding only a priority queue owns keys but never loads.
    spec = PQOnlyParent._field_specs["child"]
    expected_owns_keys, expected_pipeline_load = True, False

    # Act
    owns_keys = bool(spec.reaches & Capability.OWNS_KEYS)
    pipeline_load = bool(spec.reaches & Capability.PIPELINE_LOAD)

    # Assert
    assert owns_keys is expected_owns_keys
    assert pipeline_load is expected_pipeline_load


def test_reaches_excludes_references_root_when_only_an_sf_is_nested():
    # Arrange - SpecChild only holds an SF, no FK.
    spec = SpecParent._field_specs["child"]
    expected_references_root = False

    # Act
    references_root = bool(spec.reaches & Capability.REFERENCES_ROOT)

    # Assert
    assert references_root is expected_references_root


def test_subclass_override_rewrites_the_spec_rather_than_leaving_a_stale_one():
    # Arrange - one pop drops the inherited spec, so every axis clears together.
    class SpecOverride(SpecParent):
        refs: str = ""
        Meta: ClassVar[RedisConfig] = RedisConfig()

    expected_cleared = (False, False, False, False)

    # Act
    overridden = SpecOverride._field_specs["refs"]

    # Assert
    cleared = (
        overridden.is_special,
        overridden.is_relational,
        overridden.contains_fk,
        overridden.contains_sf,
    )
    assert cleared == expected_cleared
    assert overridden.is_redis_link is True
    # The parent keeps its own classification.
    assert "refs" in SpecParent.special_fields()
    assert SpecParent._field_specs["refs"].contains_fk


def test_safe_load_annotation_is_folded_into_the_spec():
    # Arrange
    specs = SpecParent._field_specs

    # Act / Assert
    assert specs["safe"].safe_load is True
    assert specs["plain"].safe_load is False


def test_relational_config_is_extracted_at_class_build():
    # Arrange - direct proof of ExternalFieldSpec.config; planner.py never reads it.
    expected_config = CascadeTTL(enabled=False)

    # Act
    external = CascadeBookDirect._field_specs["author"].external

    # Assert
    assert external.config == expected_config
    assert external.field_type is ForeignKey
