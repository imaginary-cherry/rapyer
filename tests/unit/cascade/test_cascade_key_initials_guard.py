"""Unit tests for validate_cascade_key_initials, driven on local model lists."""

from typing import Annotated, ClassVar

import pytest

from rapyer.base import AtomicRedisModel
from rapyer.cascade import CascadeTTL
from rapyer.cascade.planner import build_cascade_plan, validate_cascade_key_initials
from rapyer.config import RedisConfig
from rapyer.errors import CascadeKeyInitialsError
from rapyer.types.foreign_key import Reference

_GUARD_TTL = 3600
_OVERRIDDEN_INITIALS = "ZZ"


class GuardConformingTarget(AtomicRedisModel):
    """A reached target that keeps the default class_key_initials() == __name__."""

    name: str = "conforming_target"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=_GUARD_TTL, init_with_rapyer=False)


class GuardConformingOwner(AtomicRedisModel):
    """A cascade root pointing at a conforming target; both default initials."""

    ref: Annotated[Reference[GuardConformingTarget], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=_GUARD_TTL, init_with_rapyer=False)


class GuardBadReachedTarget(AtomicRedisModel):
    """
    A NON-root reached target overriding class_key_initials() to a constant
    != __name__ — the exact silent-mis-resolve seam D-02 guards. It is never a
    cascade root (it owns no cascade edge); it participates only as the target
    reached via GuardBadReachedOwner's edge, locking the participant-scope.
    """

    name: str = "bad_reached_target"

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=_GUARD_TTL, init_with_rapyer=False)

    @classmethod
    def class_key_initials(cls):
        return _OVERRIDDEN_INITIALS


class GuardBadReachedOwner(AtomicRedisModel):
    """A conforming root whose edge reaches the mis-keyed GuardBadReachedTarget."""

    ref: Annotated[Reference[GuardBadReachedTarget], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=_GUARD_TTL, init_with_rapyer=False)


class GuardBadRoot(AtomicRedisModel):
    """A cascade ROOT that itself overrides class_key_initials() != __name__."""

    ref: Annotated[Reference[GuardConformingTarget], CascadeTTL()]

    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=_GUARD_TTL, init_with_rapyer=False)

    @classmethod
    def class_key_initials(cls):
        return _OVERRIDDEN_INITIALS


def test_conforming_participant_plan_raises_nothing():
    # Arrange
    models = [GuardConformingOwner, GuardConformingTarget]

    # Act / Assert — every participant keeps class_key_initials() == __name__.
    validate_cascade_key_initials(models)


def test_override_on_reached_non_root_candidate_raises():
    # Arrange — the override lives on a target reached ONLY via an edge (non-root).
    models = [GuardBadReachedOwner, GuardBadReachedTarget]

    # Assert the plan really makes GuardBadReachedTarget a non-root participant.
    plan = build_cascade_plan(models)
    assert plan["GuardBadReachedTarget"].fks == []
    assert plan["GuardBadReachedOwner"].fks, "owner must own the reaching edge"

    # Act / Assert
    with pytest.raises(CascadeKeyInitialsError) as exc_info:
        validate_cascade_key_initials(models)

    error = exc_info.value
    assert error.model_name == "GuardBadReachedTarget"
    message = str(error)
    assert "GuardBadReachedTarget" in message
    assert _OVERRIDDEN_INITIALS in message


def test_override_on_root_participant_raises():
    # Arrange — a cascade root that mis-keys its own key prefix.
    models = [GuardBadRoot, GuardConformingTarget]

    # Act / Assert
    with pytest.raises(CascadeKeyInitialsError) as exc_info:
        validate_cascade_key_initials(models)

    assert exc_info.value.model_name == "GuardBadRoot"
    assert _OVERRIDDEN_INITIALS in str(exc_info.value)
