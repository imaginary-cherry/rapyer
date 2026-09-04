import dataclasses

import pytest

from rapyer.cascade import CascadeSpec, CascadeTTL, TTLCascadeMode
from rapyer.errors import InvalidCascadeDepthError


def test_cascade_ttl_default_values_sanity():
    # Act
    cascade_ttl = CascadeTTL()

    # Assert
    assert cascade_ttl.enabled is True
    assert cascade_ttl.depth is None
    assert cascade_ttl.mode is TTLCascadeMode.EXTEND


def test_cascade_ttl_defaults_match_explicit_construction_sanity():
    # Act / Assert
    assert CascadeTTL() == CascadeTTL(
        enabled=True, depth=None, mode=TTLCascadeMode.EXTEND
    )


def test_cascade_ttl_is_frozen_dataclass_sanity():
    # Arrange
    cascade_ttl = CascadeTTL()

    # Act / Assert
    assert dataclasses.is_dataclass(cascade_ttl)
    with pytest.raises(dataclasses.FrozenInstanceError):
        cascade_ttl.enabled = False


@pytest.mark.parametrize(["depth"], [[-1], [-10]])
def test_cascade_ttl_negative_depth_raises_sanity(depth):
    # Act / Assert
    with pytest.raises(InvalidCascadeDepthError):
        CascadeTTL(depth=depth)


@pytest.mark.parametrize(["depth"], [[0], [None], [5]])
def test_cascade_ttl_valid_depth_does_not_raise_sanity(depth):
    # Act
    cascade_ttl = CascadeTTL(depth=depth)

    # Assert
    assert cascade_ttl.depth == depth


def test_cascade_spec_negative_depth_raises_sanity():
    # Arrange
    @dataclasses.dataclass(frozen=True)
    class ConcreteCascadeSpec(CascadeSpec):
        pass

    # Act / Assert
    with pytest.raises(InvalidCascadeDepthError):
        ConcreteCascadeSpec(depth=-1)


def test_ttl_cascade_mode_has_extend_member_sanity():
    # Act / Assert
    assert TTLCascadeMode.EXTEND.value == "extend"
