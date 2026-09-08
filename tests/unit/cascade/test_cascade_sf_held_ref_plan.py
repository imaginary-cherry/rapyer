import json

import pytest

from rapyer.cascade.planner import (
    _static_walk_fk_edges,
    build_cascade_plan,
    cascade_plan_json,
    validate_cascade_ttl_targets,
)
from rapyer.errors import CascadeTargetTtlMissingError
from rapyer.types.external import Capability
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBlanketRoot,
    CascadeBookCollection,
    CascadeBookDirect,
    CascadePQRefParent,
    CascadeSetRefBlanket,
    CascadeSetRefNoTtlTarget,
    CascadeSetRefOptOut,
    CascadeSetRefParent,
    CascadeSetRefRootNoTtl,
    CascadeSetRefToNoTtl,
    CascadeSpecialChild,
)

pytestmark = pytest.mark.usefixtures("setup_fake_redis_for_cascade_models")


def test_set_held_ref_produces_one_edge_marked_set():
    # Act
    plan = build_cascade_plan([CascadeSetRefParent, CascadeAuthor])

    # Assert
    edges = plan["CascadeSetRefParent"].fks
    assert len(edges) == 1
    edge = edges[0]
    assert edge.sf_container == "set"
    assert edge.path == "refs"
    assert edge.target == "CascadeAuthor"
    assert edge.is_collection is True
    assert edge.depth is None


def test_pq_held_ref_produces_one_edge_marked_zset_with_depth():
    # Act
    plan = build_cascade_plan([CascadePQRefParent, CascadeAuthor])

    # Assert
    edges = plan["CascadePQRefParent"].fks
    assert len(edges) == 1
    edge = edges[0]
    assert edge.sf_container == "zset"
    assert edge.path == "queue"
    assert edge.target == "CascadeAuthor"
    assert edge.is_collection is True
    assert edge.depth == 2


def test_sf_edge_coexists_with_the_refresh_only_special_suffix():
    # Act
    plan = build_cascade_plan([CascadeSetRefParent, CascadeAuthor])

    # Assert
    entry = plan["CascadeSetRefParent"]
    assert entry.special_suffixes == ["refs"]
    assert len(entry.fks) == 1
    assert entry.fks[0].sf_container == "set"


def test_blanket_global_enables_sf_edge_with_global_depth():
    # Act
    plan = build_cascade_plan([CascadeSetRefBlanket, CascadeAuthor])

    # Assert
    edges = plan["CascadeSetRefBlanket"].fks
    assert len(edges) == 1
    edge = edges[0]
    assert edge.sf_container == "set"
    assert edge.depth == 2
    assert edge.resets_depth_budget is False


def test_field_opt_out_beats_enabled_global_and_emits_no_sf_edge():
    # Act
    plan = build_cascade_plan([CascadeSetRefOptOut, CascadeAuthor])

    # Assert
    assert plan["CascadeSetRefOptOut"].fks == []


def test_non_sf_edge_json_has_no_sf_container_key():
    # Act
    plan = build_cascade_plan([CascadeBookCollection, CascadeAuthor])
    payload = json.loads(cascade_plan_json(plan))

    # Assert
    edge_dict = payload["CascadeBookCollection"]["fks"][0]
    assert "sf_container" not in edge_dict


def test_inline_edge_has_none_sf_container_on_the_dataclass():
    # Act
    plan = build_cascade_plan([CascadeBlanketRoot, CascadeBookDirect, CascadeAuthor])

    # Assert
    for entry in plan.values():
        for edge in entry.fks:
            assert edge.sf_container is None


# --- Task 3: fail-fast validation regression tests for SF-held-ref targets ---


def test_sf_held_ref_target_with_no_ttl_fails_fast():
    # Arrange
    plan = build_cascade_plan([CascadeSetRefToNoTtl, CascadeSetRefNoTtlTarget])

    # Act
    with pytest.raises(CascadeTargetTtlMissingError) as exc_info:
        validate_cascade_ttl_targets(plan)

    # Assert
    assert exc_info.value.model_name == "CascadeSetRefNoTtlTarget"


def test_root_with_only_sf_edges_and_no_ttl_fails_fast():
    # Arrange
    plan = build_cascade_plan([CascadeSetRefRootNoTtl, CascadeAuthor])

    # Act
    with pytest.raises(CascadeTargetTtlMissingError) as exc_info:
        validate_cascade_ttl_targets(plan)

    # Assert
    assert exc_info.value.model_name == "CascadeSetRefRootNoTtl"


def test_positive_control_all_ttl_present_does_not_raise():
    # Arrange
    plan = build_cascade_plan([CascadeSetRefParent, CascadeAuthor])

    # Act
    validate_cascade_ttl_targets(plan)


def test_sf_of_fk_field_lands_in_both_contain_fk_and_special_fields():
    """
    Unified detection (reverses D-02): an SF-of-FK field is both a traversal edge
    source (reaches REFERENCES_ROOT) and a refresh-suffix source (own OWNS_KEYS).
    """
    # Arrange
    expected_set_field, expected_queue_field = "refs", "queue"
    set_spec = CascadeSetRefParent._field_specs[expected_set_field]
    queue_spec = CascadePQRefParent._field_specs[expected_queue_field]

    # Act / Assert
    assert (
        bool(CascadeSetRefParent.inner_capabilities() & Capability.REFERENCES_ROOT)
        is True
    )
    assert (
        bool(CascadePQRefParent.inner_capabilities() & Capability.REFERENCES_ROOT)
        is True
    )
    assert set_spec.reaches & Capability.REFERENCES_ROOT
    assert expected_set_field in CascadeSetRefParent.fields_with(Capability.OWNS_KEYS)
    assert queue_spec.reaches & Capability.REFERENCES_ROOT
    assert expected_queue_field in CascadePQRefParent.fields_with(Capability.OWNS_KEYS)


def test_plain_sf_container_is_not_an_fk_edge_but_needs_the_cascade_script():
    # Arrange - not an FK edge, but its special key still routes through the script.
    specs = CascadeSpecialChild._field_specs

    # Act / Assert
    assert not specs["tags"].reaches & Capability.REFERENCES_ROOT
    assert not specs["scores"].reaches & Capability.REFERENCES_ROOT
    assert CascadeSpecialChild._needs_cascade_script() is True


def test_nested_sf_held_ref_traversal_stays_deferred():
    # Nested SF-held refs are deferred: the SF branch fires only at top level.
    fks = []
    _static_walk_fk_edges(
        CascadeSetRefParent, "$.holder", fks, [CascadeSetRefParent], top_level=False
    )
    assert all(edge.sf_container is None for edge in fks)
