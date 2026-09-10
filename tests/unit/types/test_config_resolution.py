from typing import Annotated, ClassVar

from pydantic import Field

from rapyer.base import AtomicRedisModel, RedisConfig
from rapyer.cascade import CascadeTTL
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet


class ConfigTarget(AtomicRedisModel):
    name: str = ""
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=60)


class InnerPlacement(AtomicRedisModel):
    in_set: RedisSet[Annotated[ForeignKey[ConfigTarget], CascadeTTL(enabled=False)]] = (
        Field(default_factory=RedisSet, exclude=True)
    )
    in_queue: RedisPriorityQueue[
        Annotated[ForeignKey[ConfigTarget], CascadeTTL(depth=1)]
    ] = Field(default_factory=RedisPriorityQueue, exclude=True)
    in_list: list[Annotated[ForeignKey[ConfigTarget], CascadeTTL(depth=2)]] = Field(
        default_factory=list
    )
    in_dict: dict[str, Annotated[ForeignKey[ConfigTarget], CascadeTTL(depth=5)]] = (
        Field(default_factory=dict)
    )
    direct: Annotated[ForeignKey[ConfigTarget], CascadeTTL(depth=9)] = None
    unmarked_set: RedisSet[str] = Field(default_factory=RedisSet, exclude=True)
    unmarked_ref: ForeignKey[ConfigTarget] = None
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=60)


def _resolved(field_name: str) -> tuple:
    spec = InnerPlacement._field_specs[field_name]
    return spec.field_type.resolve_configs(InnerPlacement.__annotations__[field_name])


def test_a_config_on_the_fields_own_type_resolves():
    # Arrange
    expected_configs = (CascadeTTL(depth=9),)

    # Act
    configs = _resolved("direct")

    # Assert
    assert configs == expected_configs


def test_a_config_inside_a_special_container_resolves():
    # Arrange
    expected_set_configs = (CascadeTTL(enabled=False),)
    expected_queue_configs = (CascadeTTL(depth=1),)

    # Act
    set_configs = _resolved("in_set")
    queue_configs = _resolved("in_queue")

    # Assert
    assert set_configs == expected_set_configs
    assert queue_configs == expected_queue_configs


def test_a_config_inside_an_inline_container_resolves():
    # Arrange
    expected_list_configs = (CascadeTTL(depth=2),)

    # Act
    list_configs = _resolved("in_list")

    # Assert
    assert list_configs == expected_list_configs


def test_a_mapping_resolves_past_its_key_type_to_the_value():
    # Arrange - the key converts to RedisStr, which declares no config of its own.
    expected_configs = (CascadeTTL(depth=5),)

    # Act
    configs = _resolved("in_dict")

    # Assert
    assert configs == expected_configs


def test_a_field_with_no_marker_resolves_nothing():
    # Arrange
    expected_configs = ()

    # Act
    unmarked_set_configs = _resolved("unmarked_set")
    unmarked_ref_configs = _resolved("unmarked_ref")

    # Assert
    assert unmarked_set_configs == expected_configs
    assert unmarked_ref_configs == expected_configs


def test_element_annotations_keep_their_own_metadata():
    # Arrange
    expected_metadata = (CascadeTTL(enabled=False),)
    expected_element_count = 1
    spec = InnerPlacement._field_specs["in_set"]

    # Act
    elements = spec.field_type.element_annotations(
        InnerPlacement.__annotations__["in_set"]
    )

    # Assert
    assert len(elements) == expected_element_count
    assert elements[0].__metadata__ == expected_metadata


def test_container_kind_names_the_structure_holding_the_elements():
    # Arrange
    expected_kinds = ("set", "zset", None, None)

    # Act
    kinds = (
        RedisSet.container_kind(),
        RedisPriorityQueue.container_kind(),
        ForeignKey.container_kind(),
        InnerPlacement._field_specs["in_list"].field_type.container_kind(),
    )

    # Assert
    assert kinds == expected_kinds
