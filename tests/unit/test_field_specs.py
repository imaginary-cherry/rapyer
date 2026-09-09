from typing import Any, ClassVar, Optional

from pydantic import Field
from pydantic_core import core_schema

from rapyer.base import AtomicRedisModel, FieldSpec, RedisConfig
from rapyer.cascade import CascadeTTL
from rapyer.fields.safe_load import SafeLoad
from rapyer.types.external import ExternalFieldType
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
from rapyer.types.traits import FieldTrait
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


def _owns_keys(spec: FieldSpec) -> bool:
    return bool(
        spec.external and spec.external.field_type.traits() & FieldTrait.OWNS_KEYS
    )


def _references_root(spec: FieldSpec) -> bool:
    return bool(
        spec.external and spec.external.field_type.traits() & FieldTrait.REFERENCES_ROOT
    )


def test_fields_with_and_fields_reaching_match_a_manual_axis_scan():
    # Arrange
    specs = SpecParent._field_specs
    expected_owns_keys = {n for n, s in specs.items() if _owns_keys(s)}
    expected_links = frozenset(n for n, s in specs.items() if s.is_redis_link)
    expected_reaching_owns_keys = frozenset(
        n for n, s in specs.items() if s.reaches & FieldTrait.OWNS_KEYS
    )

    # Act / Assert
    assert set(SpecParent.fields_with(FieldTrait.OWNS_KEYS)) == expected_owns_keys
    assert SpecParent.redis_link_fields() == expected_links
    assert (
        SpecParent.fields_reaching(FieldTrait.OWNS_KEYS) == expected_reaching_owns_keys
    )


def test_redis_link_fields_is_a_strict_superset():
    # Arrange - `plain`/`safe` convert to RedisStr; `ref` joins post-A1's one peel.
    expected_links = {"plain", "ref", "refs", "child", "safe"}
    expected_field = "plain"

    # Act / Assert
    assert SpecParent.redis_link_fields() == expected_links
    assert expected_field not in SpecParent.fields_with(FieldTrait.OWNS_KEYS)


def test_each_class_caches_its_own_derived_view():
    # Arrange
    class SpecSubclass(SpecParent):
        child: str = ""
        Meta: ClassVar[RedisConfig] = RedisConfig()

    expected_field = "child"

    # Act / Assert
    assert expected_field in SpecParent.fields_reaching(FieldTrait.OWNS_KEYS)
    assert expected_field not in SpecSubclass.fields_reaching(FieldTrait.OWNS_KEYS)


def test_a_field_can_sit_on_several_axes_at_once():
    # Arrange - RedisSet[ForeignKey[...]] owns keys, reaches REFERENCES_ROOT, and is a link.
    expected_axes = (True, True, True)

    # Act
    spec = SpecParent._field_specs["refs"]

    # Assert
    axes = (
        _owns_keys(spec),
        bool(spec.reaches & FieldTrait.REFERENCES_ROOT),
        spec.is_redis_link,
    )
    assert axes == expected_axes


def test_optional_nested_model_is_seen_as_containing_a_special_field():
    # Arrange - A1 fixed: one peel strips Optional the same way the FK axis always did.
    class OptionalChildParent(AtomicRedisModel):
        child: Optional[SpecChild] = None
        Meta: ClassVar[RedisConfig] = RedisConfig()

    expected_field = "child"
    expected_reaching = frozenset({expected_field})

    # Act
    specs = OptionalChildParent._field_specs
    reaching = OptionalChildParent.fields_reaching(FieldTrait.OWNS_KEYS)

    # Assert
    assert expected_field in specs
    assert reaching == expected_reaching


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
    assert bool(spec.reaches & FieldTrait.OWNS_KEYS) is True
    assert bool(spec.reaches & FieldTrait.REFERENCES_ROOT) is True


def test_relational_trait_and_reaches_references_root_are_mutually_exclusive():
    # Arrange - a ForeignKey itself provides REFERENCES_ROOT; it does not also "reach" one.
    expected_trait, expected_reach = True, False

    # Act
    spec = SpecParent._field_specs["ref"]

    # Assert
    assert _references_root(spec) is expected_trait
    assert bool(spec.reaches & FieldTrait.REFERENCES_ROOT) is expected_reach


def test_an_unclassified_spec_is_not_kept():
    # Arrange
    plain = FieldSpec(name="x", field_type=str)
    classified = FieldSpec(name="x", field_type=str, reaches=FieldTrait.OWNS_KEYS)

    # Act / Assert
    assert plain.is_classified() is False
    assert classified.is_classified() is True


def test_reaches_carries_per_bit_precision_for_a_pq_only_subtree():
    # Arrange - a subtree holding only a priority queue owns keys but never loads.
    spec = PQOnlyParent._field_specs["child"]
    expected_owns_keys, expected_pipeline_load = True, False

    # Act
    owns_keys = bool(spec.reaches & FieldTrait.OWNS_KEYS)
    pipeline_load = bool(spec.reaches & FieldTrait.LOADS_WITH_DOC)

    # Assert
    assert owns_keys is expected_owns_keys
    assert pipeline_load is expected_pipeline_load


def test_reaches_excludes_references_root_when_only_an_sf_is_nested():
    # Arrange - SpecChild only holds an SF, no FK.
    spec = SpecParent._field_specs["child"]
    expected_references_root = False

    # Act
    references_root = bool(spec.reaches & FieldTrait.REFERENCES_ROOT)

    # Assert
    assert references_root is expected_references_root


def test_subclass_override_rewrites_the_spec_rather_than_leaving_a_stale_one():
    # Arrange - one pop drops the inherited spec, so every axis clears together.
    class SpecOverride(SpecParent):
        refs: str = ""
        Meta: ClassVar[RedisConfig] = RedisConfig()

    expected_cleared = (False, False, False)
    expected_field = "refs"

    # Act
    overridden = SpecOverride._field_specs[expected_field]

    # Assert
    cleared = (
        _owns_keys(overridden),
        bool(overridden.reaches & FieldTrait.REFERENCES_ROOT),
        bool(overridden.reaches),
    )
    assert cleared == expected_cleared
    assert overridden.is_redis_link is True
    # The parent keeps its own classification.
    assert expected_field in SpecParent.fields_with(FieldTrait.OWNS_KEYS)
    assert SpecParent._field_specs[expected_field].reaches & FieldTrait.REFERENCES_ROOT


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


def test_a_novel_external_field_type_classifies_with_zero_base_py_changes():
    # Arrange - a new kind needs one row (traits()) and zero edits to __init_subclass__.
    class NovelFieldType(ExternalFieldType[None]):
        def __init__(self, value: Any = None):
            super().__init__()
            self.value = value

        @classmethod
        def traits(cls) -> FieldTrait:
            return FieldTrait.LOADS_WITH_DOC

        @classmethod
        def __get_pydantic_core_schema__(cls, source_type, handler):
            return core_schema.no_info_plain_validator_function(
                lambda v: v if isinstance(v, cls) else cls(v),
                serialization=core_schema.plain_serializer_function_ser_schema(
                    lambda v: None
                ),
            )

    class NovelFieldModel(AtomicRedisModel):
        widget: NovelFieldType = None
        Meta: ClassVar[RedisConfig] = RedisConfig()

    expected_field, expected_trait = "widget", FieldTrait.LOADS_WITH_DOC

    # Act
    spec = NovelFieldModel._field_specs[expected_field]
    fields_with_trait = NovelFieldModel.fields_with(expected_trait)

    # Assert
    assert spec.external is not None
    assert issubclass(spec.external.field_type, NovelFieldType)
    assert spec.external.field_type.traits() == expected_trait
    assert expected_field in fields_with_trait
