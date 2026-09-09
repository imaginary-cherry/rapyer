from rapyer.types.external import ExternalFieldType, FieldTrait
from rapyer.types.foreign_key import ForeignKey
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet


def test_redis_set_pipeline_load_matches_has_lua_load_output():
    # Arrange
    expected_has_output = True

    # Act
    has_output = RedisSet.has_lua_load_output()
    has_bit = bool(RedisSet.traits() & FieldTrait.LOADS_WITH_DOC)

    # Assert
    assert has_output is expected_has_output
    assert has_bit is expected_has_output


def test_priority_queue_pipeline_load_matches_has_lua_load_output():
    # Arrange
    expected_has_output = False

    # Act
    has_output = RedisPriorityQueue.has_lua_load_output()
    has_bit = bool(RedisPriorityQueue.traits() & FieldTrait.LOADS_WITH_DOC)

    # Assert
    assert has_output is expected_has_output
    assert has_bit is expected_has_output


def test_redis_set_owns_keys_matches_owned_redis_keys():
    # Arrange
    expected_owns_keys = True

    # Act
    owns_keys = bool(RedisSet.owned_redis_keys("Model:1", ".field"))
    has_bit = bool(RedisSet.traits() & FieldTrait.OWNS_KEYS)

    # Assert
    assert owns_keys is expected_owns_keys
    assert has_bit is expected_owns_keys


def test_priority_queue_owns_keys_matches_owned_redis_keys():
    # Arrange
    expected_owns_keys = True

    # Act
    owns_keys = bool(RedisPriorityQueue.owned_redis_keys("Model:1", ".field"))
    has_bit = bool(RedisPriorityQueue.traits() & FieldTrait.OWNS_KEYS)

    # Assert
    assert owns_keys is expected_owns_keys
    assert has_bit is expected_owns_keys


def test_foreign_key_traits_is_exactly_references_root():
    # Arrange
    expected_owns_keys = False
    expected_traits = FieldTrait.REFERENCES_ROOT

    # Act
    owns_keys = bool(ForeignKey.owned_redis_keys("Model:1", ".field"))
    traits = ForeignKey.traits()

    # Assert
    assert owns_keys is expected_owns_keys
    assert traits == expected_traits


def test_external_field_type_traits_defaults_to_empty():
    # Arrange
    expected_traits = FieldTrait(0)

    # Act
    traits = ExternalFieldType.traits()

    # Assert
    assert traits == expected_traits
