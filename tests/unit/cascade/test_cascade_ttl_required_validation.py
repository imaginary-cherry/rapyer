import pytest

from rapyer.cascade.planner import (
    CascadeEdge,
    CascadePlanEntry,
    validate_cascade_ttl_targets,
)
from rapyer.errors import CascadeTargetTtlMissingError


def _plan(a_ttl, b_ttl, edge_target="B", candidates=None):
    return {
        "A": CascadePlanEntry(
            ttl=a_ttl,
            special_suffixes=[],
            fks=[
                CascadeEdge(
                    path="$.b",
                    target=edge_target,
                    is_collection=False,
                    recurse_into_target=True,
                    refresh_target_ttl=True,
                    refresh_target_special_keys=True,
                    resets_depth_budget=False,
                    candidates=candidates,
                )
            ],
        ),
        "B": CascadePlanEntry(ttl=b_ttl, special_suffixes=[], fks=[]),
    }


def test_cascade_target_ttl_missing_error_is_importable_from_rapyer_errors():
    from rapyer.errors import CascadeTargetTtlMissingError  # noqa: F401


def test_raises_when_cascade_reachable_target_has_no_ttl():
    # Arrange
    plan = _plan(a_ttl=None, b_ttl=None)

    # Act
    with pytest.raises(CascadeTargetTtlMissingError) as exc_info:
        validate_cascade_ttl_targets(plan)

    # Assert
    assert exc_info.value.model_name == "B"


def test_raises_on_a_non_first_candidate_that_lacks_ttl():
    # Arrange
    plan = {
        "A": CascadePlanEntry(
            ttl=30,
            special_suffixes=[],
            fks=[
                CascadeEdge(
                    path="$.ref",
                    target="First",
                    is_collection=False,
                    recurse_into_target=True,
                    refresh_target_ttl=True,
                    refresh_target_special_keys=True,
                    resets_depth_budget=False,
                    candidates=["First", "Second"],
                )
            ],
        ),
        "First": CascadePlanEntry(ttl=60, special_suffixes=[], fks=[]),
        "Second": CascadePlanEntry(ttl=None, special_suffixes=[], fks=[]),
    }

    # Act
    with pytest.raises(CascadeTargetTtlMissingError) as exc_info:
        validate_cascade_ttl_targets(plan)

    # Assert
    assert exc_info.value.model_name == "Second"


def test_does_not_raise_when_target_ttl_is_set():
    # Arrange
    # The root ("A") also refreshes its own key, so it must carry a ttl
    # too — give it one here so this test isolates the TARGET-ttl-set path.
    plan = _plan(a_ttl=30, b_ttl=60)

    # Act
    validate_cascade_ttl_targets(plan)


def test_raises_when_cascade_root_has_edges_but_no_ttl():
    # Arrange
    # A root with outgoing cascade-enabled edges but Meta.ttl=None passed the
    # old TARGET-only validator, then blew up at apply time EXPIREing its own
    # key with a nil ttl. It must now be rejected up front.
    plan = _plan(a_ttl=None, b_ttl=60)

    # Act
    with pytest.raises(CascadeTargetTtlMissingError) as exc_info:
        validate_cascade_ttl_targets(plan)

    # Assert
    assert exc_info.value.model_name == "A"


def test_raises_rapyer_error_when_edge_target_absent_from_partial_plan():
    # Arrange
    # A plan built from a subset of models can reference a target class that is
    # not itself in the plan; the lookup must raise a RapyerError, not a bare
    # KeyError.
    partial_plan = {
        "A": CascadePlanEntry(
            ttl=60,
            special_suffixes=[],
            fks=[
                CascadeEdge(
                    path="$.b",
                    target="MissingTarget",
                    is_collection=False,
                    recurse_into_target=True,
                    refresh_target_ttl=True,
                    refresh_target_special_keys=True,
                    resets_depth_budget=False,
                )
            ],
        )
    }

    # Act
    with pytest.raises(CascadeTargetTtlMissingError) as exc_info:
        validate_cascade_ttl_targets(partial_plan)

    # Assert
    assert exc_info.value.model_name == "MissingTarget"


def test_does_not_raise_for_a_class_never_reached_as_a_target_even_with_no_ttl():
    # Arrange
    plan = {
        "A": CascadePlanEntry(ttl=None, special_suffixes=[], fks=[]),
    }

    # Act
    validate_cascade_ttl_targets(plan)


def test_raises_on_first_violation_deterministically_sorted_by_class_name():
    # Arrange
    plan = {
        "A": CascadePlanEntry(
            ttl=None,
            special_suffixes=[],
            fks=[
                CascadeEdge(
                    path="$.z",
                    target="Z",
                    is_collection=False,
                    recurse_into_target=True,
                    refresh_target_ttl=True,
                    refresh_target_special_keys=True,
                    resets_depth_budget=False,
                )
            ],
        ),
        "M": CascadePlanEntry(
            ttl=None,
            special_suffixes=[],
            fks=[
                CascadeEdge(
                    path="$.y",
                    target="Y",
                    is_collection=False,
                    recurse_into_target=True,
                    refresh_target_ttl=True,
                    refresh_target_special_keys=True,
                    resets_depth_budget=False,
                )
            ],
        ),
        "Y": CascadePlanEntry(ttl=None, special_suffixes=[], fks=[]),
        "Z": CascadePlanEntry(ttl=None, special_suffixes=[], fks=[]),
    }

    # Act
    with pytest.raises(CascadeTargetTtlMissingError) as exc_info:
        validate_cascade_ttl_targets(plan)

    # Assert
    # "A" sorts before "M" — A's edge (target "Z") must be the first violation.
    assert exc_info.value.model_name == "Z"
