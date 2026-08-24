from unittest.mock import MagicMock

import pytest

from rapyer.config import (
    FROZEN_EXEMPT_FIELDS,
    RESOLVABLE_FIELDS,
    RedisConfig,
)
from rapyer.errors import MetaFrozenError, UnsupportedArgumentValueError


def _config() -> RedisConfig:
    return RedisConfig(redis=MagicMock())


def test_policy_sets_are_derived_from_field_annotations():
    assert FROZEN_EXEMPT_FIELDS == frozenset({"cascade_function_name"})
    assert RESOLVABLE_FIELDS == frozenset({"vectorizer"})


def test_frozen_exempt_field_stays_writable_while_locked():
    config = _config()
    config._meta_locked = True

    config.cascade_function_name = "rapyer_cascade_abc"

    assert config.cascade_function_name == "rapyer_cascade_abc"


def test_non_exempt_field_raises_while_locked():
    config = _config()
    config._meta_locked = True

    with pytest.raises(MetaFrozenError):
        config.ttl = 60


def test_private_attrs_stay_writable_while_locked():
    config = _config()
    config._meta_locked = True

    config._meta_locked = False

    assert config._meta_locked is False


def test_resolve_rejects_a_field_not_marked_resolvable():
    config = _config()

    with pytest.raises(UnsupportedArgumentValueError):
        config._resolve("ttl", 60)


def test_resolve_does_not_mark_the_field_preset():
    config = _config()
    adapter = MagicMock()

    config._resolve("vectorizer", adapter)

    assert config.vectorizer is adapter
    assert config.is_preset("vectorizer") is False


def test_direct_assignment_marks_the_field_preset():
    config = _config()

    config.vectorizer = MagicMock()

    assert config.is_preset("vectorizer") is True


def test_constructor_value_marks_the_field_preset():
    config = RedisConfig(redis=MagicMock(), vectorizer=MagicMock())

    assert config.is_preset("vectorizer") is True


def test_resolve_raises_while_locked():
    config = _config()
    config._meta_locked = True

    with pytest.raises(MetaFrozenError):
        config._resolve("vectorizer", MagicMock())
