from rapyer.cascade.planner import build_cascade_plan, cascade_plan_json
from rapyer.scripts.loader import build_cascade_library
from tests.models.cascade_types import ALL_CASCADE_MODELS


def test_cascade_library_source_has_all_tokens_substituted():
    # Arrange
    plan_json = cascade_plan_json(build_cascade_plan(ALL_CASCADE_MODELS))

    # Act
    library_name, function_name, source = build_cascade_library(plan_json)

    # Assert
    # Real FUNCTION LOAD validation lives in the integration suite.
    assert source.splitlines()[0] == f"#!lua name={library_name}"
    assert "RAPYER_CASCADE_PLAN_LITERAL" not in source
    assert "RAPYER_CASCADE_LIB" not in source
    assert "RAPYER_CASCADE_FN" not in source
    assert function_name in source
    assert "register_function" in source
