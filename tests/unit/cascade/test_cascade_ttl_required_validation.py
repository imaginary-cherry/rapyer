import pytest

from rapyer.cascade.planner import validate_cascade_ttl_targets
from rapyer.errors import CascadeTargetTtlMissingError


def _plan(a_ttl, b_ttl, edge_target="B"):
    return {
        "A": {
            "ttl": a_ttl,
            "special_suffixes": [],
            "fks": [
                {
                    "path": "$.b",
                    "target": edge_target,
                    "collection": False,
                    "recurse": True,
                    "ttl": True,
                    "special": True,
                }
            ],
        },
        "B": {"ttl": b_ttl, "special_suffixes": [], "fks": []},
    }


def test_cascade_target_ttl_missing_error_is_importable_from_rapyer_errors():
    from rapyer.errors import CascadeTargetTtlMissingError  # noqa: F401


def test_raises_when_cascade_reachable_target_has_no_ttl():
    plan = _plan(a_ttl=None, b_ttl=None)

    with pytest.raises(CascadeTargetTtlMissingError) as exc_info:
        validate_cascade_ttl_targets(plan)
    assert exc_info.value.model_name == "B"


def test_does_not_raise_when_target_ttl_is_set():
    # WR-02: the root ("A") also refreshes its own key, so it must carry a ttl
    # too — give it one here so this test isolates the TARGET-ttl-set path.
    plan = _plan(a_ttl=30, b_ttl=60)

    validate_cascade_ttl_targets(plan)


def test_wr02_raises_when_cascade_root_has_edges_but_no_ttl():
    # A root with outgoing cascade-enabled edges but Meta.ttl=None passed the
    # old TARGET-only validator, then blew up at apply time EXPIREing its own
    # key with a nil ttl. It must now be rejected up front.
    plan = _plan(a_ttl=None, b_ttl=60)

    with pytest.raises(CascadeTargetTtlMissingError) as exc_info:
        validate_cascade_ttl_targets(plan)
    assert exc_info.value.model_name == "A"


def test_wr03_raises_rapyer_error_when_edge_target_absent_from_partial_plan():
    # A plan built from a subset of models can reference a target class that is
    # not itself in the plan; the lookup must raise a RapyerError, not a bare
    # KeyError.
    partial_plan = {
        "A": {
            "ttl": 60,
            "special_suffixes": [],
            "fks": [
                {
                    "path": "$.b",
                    "target": "MissingTarget",
                    "collection": False,
                    "recurse": True,
                    "ttl": True,
                    "special": True,
                }
            ],
        }
    }

    with pytest.raises(CascadeTargetTtlMissingError) as exc_info:
        validate_cascade_ttl_targets(partial_plan)
    assert exc_info.value.model_name == "MissingTarget"


def test_does_not_raise_for_a_class_never_reached_as_a_target_even_with_no_ttl():
    plan = {
        "A": {"ttl": None, "special_suffixes": [], "fks": []},
    }

    validate_cascade_ttl_targets(plan)


def test_raises_on_first_violation_deterministically_sorted_by_class_name():
    plan = {
        "A": {
            "ttl": None,
            "special_suffixes": [],
            "fks": [
                {
                    "path": "$.z",
                    "target": "Z",
                    "collection": False,
                    "recurse": True,
                    "ttl": True,
                    "special": True,
                }
            ],
        },
        "M": {
            "ttl": None,
            "special_suffixes": [],
            "fks": [
                {
                    "path": "$.y",
                    "target": "Y",
                    "collection": False,
                    "recurse": True,
                    "ttl": True,
                    "special": True,
                }
            ],
        },
        "Y": {"ttl": None, "special_suffixes": [], "fks": []},
        "Z": {"ttl": None, "special_suffixes": [], "fks": []},
    }

    with pytest.raises(CascadeTargetTtlMissingError) as exc_info:
        validate_cascade_ttl_targets(plan)
    # "A" sorts before "M" — A's edge (target "Z") must be the first violation.
    assert exc_info.value.model_name == "Z"
