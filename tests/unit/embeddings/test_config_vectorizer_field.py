import pytest

from rapyer.config import RedisConfig
from rapyer.errors import MetaFrozenError


class _FakeEmbeddingAdapter:
    """Minimal EmbeddingAdapter double - structurally matches the Protocol."""

    @property
    def dims(self):
        return 3

    async def aembed(self, content):
        return [0.1, 0.2, 0.3]

    async def aembed_many(self, contents):
        return [[0.1, 0.2, 0.3] for _ in contents]


def test_redis_config_vectorizer_defaults_to_none_unresolved_sanity():
    # Act
    config = RedisConfig()

    # Assert
    assert config.vectorizer is None
    assert config._vectorizer_preset is False


def test_redis_config_vectorizer_constructor_kwarg_flags_preset_sanity():
    # Arrange
    adapter = _FakeEmbeddingAdapter()

    # Act
    config = RedisConfig(vectorizer=adapter)

    # Assert
    assert config.vectorizer is adapter
    assert config._vectorizer_preset is True


def test_redis_config_vectorizer_post_construction_assignment_flags_preset_sanity():
    # Arrange
    adapter = _FakeEmbeddingAdapter()
    config = RedisConfig()

    # Act
    config.vectorizer = adapter

    # Assert
    assert config.vectorizer is adapter
    assert config._vectorizer_preset is True


def test_redis_config_vectorizer_assignment_raises_when_meta_locked_sanity():
    # Arrange
    adapter = _FakeEmbeddingAdapter()
    config = RedisConfig()
    config._meta_locked = True

    # Act + Assert
    with pytest.raises(MetaFrozenError):
        config.vectorizer = adapter


def test_resolve_vectorizer_sets_value_without_flagging_preset_sanity():
    # Arrange
    adapter = _FakeEmbeddingAdapter()
    config = RedisConfig()

    # Act
    config._resolve_vectorizer(adapter)

    # Assert
    assert config.vectorizer is adapter
    assert config._vectorizer_preset is False


def test_resolve_vectorizer_raises_when_meta_locked_sanity():
    # Arrange
    adapter = _FakeEmbeddingAdapter()
    config = RedisConfig()
    config._meta_locked = True

    # Act + Assert
    with pytest.raises(MetaFrozenError):
        config._resolve_vectorizer(adapter)
