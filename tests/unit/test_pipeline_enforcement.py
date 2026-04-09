import pytest

import tests.integration.pipeline.test__update_method_dont_set_redis  # noqa: F401
import tests.integration.pipeline.test_pipeline_asave_batching  # noqa: F401
import tests.integration.pipeline.test_pipeline_context_manager_atomic_operations  # noqa: F401
import tests.integration.pipeline.test_pipeline_coverage_gaps  # noqa: F401
import tests.integration.pipeline.test_pipeline_model_changes_sync  # noqa: F401
import tests.integration.pipeline.test_pipeline_non_redis_types_operations  # noqa: F401
import tests.integration.pipeline.test_pipeline_noscript_recovery  # noqa: F401
import tests.integration.pipeline.test_redis_bytes_pipeline  # noqa: F401
import tests.integration.pipeline.test_redis_datetime_pipeline  # noqa: F401
import tests.integration.pipeline.test_redis_float_pipeline  # noqa: F401
import tests.integration.pipeline.test_redis_int_pipeline  # noqa: F401
import tests.integration.pipeline.test_redis_list_pipeline  # noqa: F401
import tests.integration.pipeline.test_redis_str_pipeline  # noqa: F401
from rapyer.types.base import RedisType
from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetime, RedisDatetimeTimestamp
from rapyer.types.dct import RedisDict
from rapyer.types.float import RedisFloat
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.string import RedisStr
from tests.conftest import (
    MODEL_PIPELINE_TESTED_METHODS,
    STANDALONE_PIPELINE_TESTED_METHODS,
    get_all_type_methods,
    method_to_tuple,
)

PIPELINE_TYPES = [
    RedisType,
    RedisInt,
    RedisFloat,
    RedisStr,
    RedisBytes,
    RedisDatetime,
    RedisDatetimeTimestamp,
    RedisList,
    RedisDict,
]

EXCLUDED_METHODS = [
    # Not pipeline-aware — uses self.redis directly, not self.client
    RedisList.apop,
    # Lua script returns value; can't defer execution in pipeline
    RedisDict.apop,
    RedisDict.apopitem,
    # Read-only operation — no mutation to verify
    RedisType.aload,
    # Internal/utility methods — not Redis operations
    RedisType.clone,
    RedisType.serialize_unknown,
    RedisType.deserialize_unknown,
    RedisInt.clone,
    RedisFloat.clone,
    RedisStr.clone,
    RedisBytes.clone,
    RedisDatetime.clone,
    RedisList.clone,
    RedisDict.clone,
    RedisList.__init__,
    RedisDict.__init__,
    RedisList.create_new_value,
    RedisList.create_new_values,
    RedisList.iterate_items,
    RedisList.sub_field_path,
    RedisDict.iterate_items,
    RedisDict.validate_dict,
]

EXCLUDED_FROM_PIPELINE_TEST = {method_to_tuple(m) for m in EXCLUDED_METHODS}


def collect_all_pipeline_methods():
    all_methods = set()
    for cls in PIPELINE_TYPES:
        all_methods.update(get_all_type_methods(cls))
    return sorted(m for m in all_methods if m not in EXCLUDED_FROM_PIPELINE_TEST)


@pytest.mark.parametrize(["class_name", "method_name"], collect_all_pipeline_methods())
def test_method_has_model_pipeline_test_coverage(class_name, method_name):
    # Arrange
    expected_entry = (class_name, method_name)

    # Act
    has_coverage = expected_entry in MODEL_PIPELINE_TESTED_METHODS

    # Assert
    assert has_coverage, (
        f"Method {class_name}.{method_name} needs a model.apipeline() test.\n"
        f"Add @model_pipeline_test_for({class_name}.{method_name}) to a test.\n"
        f"Or add to EXCLUDED_METHODS with justification."
    )


@pytest.mark.parametrize(["class_name", "method_name"], collect_all_pipeline_methods())
def test_method_has_standalone_pipeline_test_coverage(class_name, method_name):
    # Arrange
    expected_entry = (class_name, method_name)

    # Act
    has_coverage = expected_entry in STANDALONE_PIPELINE_TESTED_METHODS

    # Assert
    assert has_coverage, (
        f"Method {class_name}.{method_name} needs a rapyer.apipeline() test.\n"
        f"Add @standalone_pipeline_test_for({class_name}.{method_name}) to a test.\n"
        f"Or add to EXCLUDED_METHODS with justification."
    )
