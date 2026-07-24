import json

import pytest

from rapyer.cascade.planner import (
    build_cascade_plan,
    cascade_plan_json,
    validate_cascade_ttl_targets,
)
from rapyer.errors import CascadeTargetTtlMissingError
from rapyer.types.priority_queue import RedisPriorityQueue
from rapyer.types.redis_set import RedisSet
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


def test_guard_redis_set_contains_fk_field_is_false_and_field_not_in_contain_fk():
    # Guards D-02: the SF edge comes from _special_field_names, not _contain_fk.
    assert RedisSet.contains_fk_field() is False
    assert RedisPriorityQueue.contains_fk_field() is False
    assert "refs" not in CascadeSetRefParent._contain_fk
    assert "refs" in CascadeSetRefParent._special_field_names
