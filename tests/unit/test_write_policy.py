from unittest.mock import MagicMock

import pytest

from rapyer.config import DEFAULT_WRITE_POLICY, RedisConfig, WritePolicy, policy_for
from rapyer.errors import MetaFrozenError, UnsupportedArgumentValueError


def _config() -> RedisConfig:
    return RedisConfig(redis=MagicMock())


def _locked_config() -> RedisConfig:
    config = _config()
    config._meta_locked = True
    return config


def test_policy_comes_from_the_field_annotation():
    assert policy_for(RedisConfig, "cascade_function_name") == WritePolicy(
        frozen_exempt=True
    )
    assert policy_for(RedisConfig, "vectorizer") == WritePolicy(resolvable=True)


def test_unannotated_field_gets_the_strict_default_policy():
    assert policy_for(RedisConfig, "max_delete_per_transaction") is DEFAULT_WRITE_POLICY
    assert DEFAULT_WRITE_POLICY.frozen_exempt is False
    assert DEFAULT_WRITE_POLICY.resolvable is False


def test_unannotated_field_is_still_frozen_at_runtime():
    # The point of the default policy: forgetting an annotation must not lose the guard.
    config = _locked_config()

    with pytest.raises(MetaFrozenError):
        config.max_delete_per_transaction = 5


def test_blocked_write_does_not_change_the_value():
    config = _config()
    config.ttl = 60
    config._meta_locked = True

    with pytest.raises(MetaFrozenError):
        config.ttl = 999

    assert config.ttl == 60


def test_frozen_exempt_field_stays_writable_while_locked():
    config = _locked_config()

    config.cascade_function_name = "rapyer_cascade_abc"

    assert config.cascade_function_name == "rapyer_cascade_abc"


def test_private_attrs_stay_writable_while_locked():
    config = _locked_config()

    config._meta_locked = False

    assert config._meta_locked is False


def test_construction_is_not_blocked_by_the_guard():
    config = RedisConfig(redis=MagicMock(), ttl=30)

    assert config.ttl == 30


def test_write_policy_resolve_rejects_a_field_not_marked_resolvable():
    config = _config()

    with pytest.raises(UnsupportedArgumentValueError):
        policy_for(RedisConfig, "ttl").resolve(config, "ttl", 60)


def test_resolve_vectorizer_does_not_mark_the_field_preset():
    config = _config()
    adapter = MagicMock()

    config.resolve_vectorizer(adapter)

    assert config.vectorizer is adapter
    assert config.is_preset("vectorizer") is False


def test_direct_assignment_marks_the_field_preset():
    config = _config()

    config.vectorizer = MagicMock()

    assert config.is_preset("vectorizer") is True


def test_constructor_value_marks_the_field_preset():
    config = RedisConfig(redis=MagicMock(), vectorizer=MagicMock())

    assert config.is_preset("vectorizer") is True


def test_resolve_vectorizer_raises_while_locked():
    config = _locked_config()

    with pytest.raises(MetaFrozenError):
        config.resolve_vectorizer(MagicMock())


def test_resolve_vectorizer_keeps_a_value_the_user_already_set():
    config = RedisConfig(redis=MagicMock(), vectorizer="user-choice")

    config.resolve_vectorizer("init-default")

    assert config.vectorizer == "user-choice"


def test_is_preset_rejects_an_unknown_field_name():
    config = _config()

    with pytest.raises(UnsupportedArgumentValueError):
        config.is_preset("vectorizr")
