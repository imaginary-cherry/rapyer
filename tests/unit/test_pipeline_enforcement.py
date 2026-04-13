import pytest

import rapyer.types  # noqa: F401  # ensure every BaseRedisType subclass is registered
import tests.integration.pipeline.test__update_method_dont_set_redis  # noqa: F401
import tests.integration.pipeline.test_pipeline_adelete_many  # noqa: F401
import tests.integration.pipeline.test_pipeline_asave_batching  # noqa: F401
import tests.integration.pipeline.test_pipeline_atomic_model_actions  # noqa: F401
import tests.integration.pipeline.test_pipeline_context_manager_atomic_operations  # noqa: F401
import tests.integration.pipeline.test_pipeline_model_changes_sync  # noqa: F401
import tests.integration.pipeline.test_pipeline_non_redis_types_operations  # noqa: F401
import tests.integration.pipeline.test_pipeline_noscript_recovery  # noqa: F401
import tests.integration.pipeline.test_pipeline_set_ttl  # noqa: F401
import tests.integration.pipeline.test_redis_bytes_pipeline  # noqa: F401
import tests.integration.pipeline.test_redis_datetime_pipeline  # noqa: F401
import tests.integration.pipeline.test_redis_float_pipeline  # noqa: F401
import tests.integration.pipeline.test_redis_int_pipeline  # noqa: F401
import tests.integration.pipeline.test_redis_list_pipeline  # noqa: F401
import tests.integration.pipeline.test_redis_str_pipeline  # noqa: F401
from rapyer.base import AtomicRedisModel
from rapyer.types.base import BaseRedisType
from tests.conftest import (
    MODEL_PIPELINE_TESTED_METHODS,
    STANDALONE_PIPELINE_TESTED_METHODS,
    get_all_type_methods,
    get_async_methods,
)
from tests.unit.enforcement_exclusions import (
    BASE_TYPE_INTERNAL_METHODS,
    MODEL_INDEX_METHODS,
    MODEL_INTERNAL_METHODS,
    MODEL_QUERY_METHODS,
    MODEL_READ_METHODS,
    PQ_READ_METHODS,
    PQ_WRITE_METHODS,
    SPECIAL_FIELD_LIFECYCLE_METHODS,
    TYPE_INTERNAL_METHODS,
    TYPE_READ_METHODS,
)

EXCLUDED_FROM_TYPE_PIPELINE_TEST = (
    TYPE_INTERNAL_METHODS  # Not Redis operations
    | TYPE_READ_METHODS  # Return values, can't defer in pipeline
    | BASE_TYPE_INTERNAL_METHODS  # Construction / path / abstract helpers
    | PQ_READ_METHODS  # Return values, can't defer in pipeline
    | PQ_WRITE_METHODS  # Ignore write methods as well for now
    | SPECIAL_FIELD_LIFECYCLE_METHODS  # Lifecycle hooks, covered by model tests
)

EXCLUDED_FROM_MODEL_PIPELINE_TEST = (
    MODEL_READ_METHODS  # No mutation to verify
    | MODEL_QUERY_METHODS  # No mutation to verify
    | MODEL_INDEX_METHODS  # Schema ops, not data
    | MODEL_INTERNAL_METHODS  # Internal query helpers
)


def _all_subclasses(cls):
    result = set()
    for sub in cls.__subclasses__():
        result.add(sub)
        result.update(_all_subclasses(sub))
    return result


def collect_all_pipeline_methods():
    all_methods = set()
    for cls in _all_subclasses(BaseRedisType):
        all_methods.update(get_all_type_methods(cls))
    all_methods.update(get_async_methods(AtomicRedisModel))
    excluded = EXCLUDED_FROM_TYPE_PIPELINE_TEST | EXCLUDED_FROM_MODEL_PIPELINE_TEST
    return sorted(m for m in all_methods if m not in excluded)


@pytest.mark.parametrize(["class_name", "method_name"], collect_all_pipeline_methods())
def test_method_has_pipeline_test_coverage(class_name, method_name):
    # Arrange
    expected_entry = (class_name, method_name)

    # Act
    has_coverage = (
        expected_entry in MODEL_PIPELINE_TESTED_METHODS
        or expected_entry in STANDALONE_PIPELINE_TESTED_METHODS
    )

    # Assert
    assert has_coverage, (
        f"Method {class_name}.{method_name} needs a pipeline atomicity test.\n"
        f"Add @model_pipeline_test_for({class_name}.{method_name}) or "
        f"@standalone_pipeline_test_for({class_name}.{method_name}) to a test.\n"
        f"Or add to the appropriate group in enforcement_exclusions.py with justification."
    )
