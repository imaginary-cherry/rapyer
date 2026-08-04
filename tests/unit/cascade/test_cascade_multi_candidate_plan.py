import pytest

from rapyer.cascade.planner import build_cascade_plan
from tests.unit.cascade.conftest import CASCADE_PLANNER_MODELS
from tests.models.cascade_types import (
    CascadeBlanketLeaf,
    CascadeBlanketRoot,
    CascadePolyBase,
    CascadePolyDedupOwner,
    CascadePolyOwner,
    CascadePolySub1,
    CascadePolySub2,
    CascadeUnionMemberA,
    CascadeUnionMemberB,
    CascadeUnionOwner,
)

pytestmark = pytest.mark.usefixtures("setup_fake_redis_for_cascade_models")


def test_scalar_union_fk_lists_every_candidate():
    # Act
    plan = build_cascade_plan(
        [CascadeUnionOwner, CascadeUnionMemberA, CascadeUnionMemberB]
    )

    # Assert
    edges = plan["CascadeUnionOwner"].fks
    assert len(edges) == 1
    edge = edges[0]
    assert edge.path == "$.ref"
    # Both union members are candidates, in declaration order; target is the first.
    assert edge.candidates == ["CascadeUnionMemberA", "CascadeUnionMemberB"]
    assert edge.target == "CascadeUnionMemberA"


def test_single_target_edge_is_unchanged_with_none_candidates():
    # Act
    plan = build_cascade_plan([CascadeBlanketRoot, CascadeBlanketLeaf])

    # Assert
    # A pre-existing single-target edge keeps its scalar target and carries no
    # candidates list (byte-identity preserved: candidates=None is dropped).
    edge = plan["CascadeBlanketRoot"].fks[0]
    assert edge.target == "CascadeBlanketLeaf"
    assert edge.candidates is None


def test_polymorphic_base_fk_enumerates_base_and_all_subclasses():
    # Act
    plan = build_cascade_plan(
        [CascadePolyOwner, CascadePolyBase, CascadePolySub1, CascadePolySub2]
    )

    # Assert
    # Base included (Decision #3: registered, ttl-bearing) plus every subclass
    # enumerated from the threaded models list — three candidates, not one.
    edge = plan["CascadePolyOwner"].fks[0]
    assert set(edge.candidates) == {
        "CascadePolyBase",
        "CascadePolySub1",
        "CascadePolySub2",
    }
    assert len(edge.candidates) == 3


def test_candidate_ordering_is_declaration_order_with_target_first():
    # Act
    plan = build_cascade_plan(
        [CascadePolyOwner, CascadePolyBase, CascadePolySub1, CascadePolySub2]
    )

    # Assert
    edge = plan["CascadePolyOwner"].fks[0]
    assert edge.candidates == [
        "CascadePolyBase",
        "CascadePolySub1",
        "CascadePolySub2",
    ]
    assert edge.target == edge.candidates[0]


def test_candidates_are_deduplicated_when_reachable_via_two_paths():
    # Act
    plan = build_cascade_plan(
        [CascadePolyDedupOwner, CascadePolyBase, CascadePolySub1, CascadePolySub2]
    )

    # Assert
    # CascadePolySub1 is both a listed union member and a subclass of the base;
    # it must appear exactly once, order-preserving.
    edge = plan["CascadePolyDedupOwner"].fks[0]
    assert edge.candidates == [
        "CascadePolyBase",
        "CascadePolySub1",
        "CascadePolySub2",
    ]
    assert edge.candidates.count("CascadePolySub1") == 1


def test_base_with_no_registered_subclasses_degrades_to_single_target():
    # Act
    # Option B threading: subclasses absent from the passed models list are not
    # enumerated, so a base with no reachable subclasses degrades to a single
    # target (candidates dropped, byte-identical).
    plan = build_cascade_plan([CascadePolyOwner, CascadePolyBase])

    # Assert
    edge = plan["CascadePolyOwner"].fks[0]
    assert edge.target == "CascadePolyBase"
    assert edge.candidates is None


def test_no_preexisting_single_target_model_is_silently_expanded():
    # Assert (Assumption A2)
    # Every model that shipped before this phase is single-target; none of them
    # has registered subclasses or a union FK, so the subclass-expansion rule
    # must leave every pre-existing edge with candidates=None (byte-identity).
    plan = build_cascade_plan(CASCADE_PLANNER_MODELS)
    for class_name, entry in plan.items():
        for edge in entry.fks:
            assert edge.candidates is None, (class_name, edge.path)
