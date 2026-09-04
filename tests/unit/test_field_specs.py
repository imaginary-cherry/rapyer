from typing import ClassVar, Optional

from rapyer.base import AtomicRedisModel, FieldSpec, RedisConfig
from rapyer.cascade import CascadeTTL
from rapyer.fields.safe_load import SafeLoad
from rapyer.types.foreign_key import ForeignKey
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


def test_derived_views_match_their_axis_on_the_specs():
    specs = SpecParent._field_specs

    assert set(SpecParent.special_fields()) == {
        n for n, s in specs.items() if s.special is not None
    }
    assert SpecParent.redis_link_fields() == frozenset(
        n for n, s in specs.items() if s.is_redis_link
    )
    assert SpecParent.fields_containing_sf() == frozenset(
        n for n, s in specs.items() if s.contains_sf
    )


def test_redis_link_fields_is_a_strict_superset():
    # `plain`/`safe` convert to RedisStr, so they're links on no other axis.
    assert SpecParent.redis_link_fields() == {"plain", "refs", "child", "safe"}
    assert "plain" not in SpecParent.special_fields()


def test_each_class_caches_its_own_derived_view():
    class SpecSubclass(SpecParent):
        child: str = ""
        Meta: ClassVar[RedisConfig] = RedisConfig()

    assert "child" in SpecParent.fields_containing_sf()
    assert "child" not in SpecSubclass.fields_containing_sf()


def test_a_field_can_sit_on_several_axes_at_once():
    # RedisSet[ForeignKey[...]] sits on special AND contains_fk AND link at once.
    spec = SpecParent._field_specs["refs"]

    assert spec.special is not None
    assert spec.contains_fk is True
    assert spec.is_redis_link is True
    assert spec.relational is None


def test_optional_nested_model_is_not_seen_as_containing_a_special_field():
    # A1, pinned deliberately: FK axes strip Optional first, containment axes don't.
    class OptionalChildParent(AtomicRedisModel):
        child: Optional[SpecChild] = None
        Meta: ClassVar[RedisConfig] = RedisConfig()

    assert "child" not in OptionalChildParent._field_specs
    assert OptionalChildParent.fields_containing_sf() == frozenset()


def test_relational_and_contains_fk_are_mutually_exclusive():
    # A ForeignKey itself is relational; it does not also "contain" one.
    assert SpecParent._field_specs["ref"].relational is not None
    assert SpecParent._field_specs["ref"].contains_fk is False


def test_an_unclassified_spec_is_not_kept():
    assert FieldSpec(name="x", field_type=str).is_classified() is False
    assert FieldSpec(name="x", field_type=str, contains_sf=True).is_classified() is True


def test_subclass_override_rewrites_the_spec_rather_than_leaving_a_stale_one():
    class SpecOverride(SpecParent):
        refs: str = ""
        Meta: ClassVar[RedisConfig] = RedisConfig()

    # One pop drops the inherited spec, so every axis it was on clears together.
    overridden = SpecOverride._field_specs["refs"]
    assert overridden.special is None
    assert overridden.relational is None
    assert overridden.contains_fk is False
    assert overridden.contains_sf is False
    assert overridden.is_redis_link is True
    # The parent keeps its own classification.
    assert "refs" in SpecParent.special_fields()
    assert SpecParent._field_specs["refs"].contains_fk


def test_safe_load_annotation_is_folded_into_the_spec():
    assert SpecParent._field_specs["safe"].safe_load is True
    assert SpecParent._field_specs["plain"].safe_load is False


def test_relational_config_is_extracted_at_class_build():
    # Direct proof of RelationalFieldSpec.config; planner.py never reads it.
    spec = CascadeBookDirect._field_specs["author"].relational

    assert spec.config == CascadeTTL(enabled=False)
    assert spec.field_type is ForeignKey
