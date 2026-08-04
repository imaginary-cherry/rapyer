import pytest

from rapyer.cascade.planner import build_cascade_plan
from tests.models.cascade_types import (
    CascadeBlanketLeaf,
    CascadeBlanketRoot,
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
