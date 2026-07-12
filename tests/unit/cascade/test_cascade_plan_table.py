import pytest

from rapyer.base import REDIS_MODELS
from rapyer.cascade.planner import CascadePlanEntry, build_cascade_plan
from tests.models.cascade_types import (
    CASCADE_FIXTURE_TTL_SECONDS,
    CascadeAuthor,
    CascadeBlanketLeaf,
    CascadeBlanketRoot,
    CascadeBookCollection,
    CascadeBookDirect,
    CascadeBookNested,
    CascadeProfile,
)
from tests.models.special_types import PQContainerModel, PriorityQueueModel
from tests.unit.cascade.conftest import CASCADE_PLANNER_MODELS

pytestmark = pytest.mark.usefixtures("setup_fake_redis_for_cascade_models")


def test_build_cascade_plan_is_importable():
    from rapyer.cascade.planner import build_cascade_plan  # noqa: F401


def test_every_model_gets_exactly_one_entry_even_a_plain_leaf():
    plan = build_cascade_plan([CascadeAuthor])

    # CascadeAuthor now carries CASCADE_FIXTURE_TTL_SECONDS so it
    # can never fail a nil-ttl target/root check; read the ttl back off the
    # class itself rather than hardcoding a stale None.
    assert plan == {
        "CascadeAuthor": CascadePlanEntry(
            ttl=CascadeAuthor.Meta.ttl,
            special_suffixes=[],
            fks=[],
        )
    }


def test_shape1_disabled_field_produces_no_edge():
    plan = build_cascade_plan([CascadeBookDirect, CascadeAuthor])

    assert plan["CascadeBookDirect"].fks == []


def test_shape1_blanket_enabled_produces_one_edge_with_global_depth():
    plan = build_cascade_plan([CascadeBlanketRoot, CascadeBlanketLeaf])

    edges = plan["CascadeBlanketRoot"].fks
    assert len(edges) == 1
    edge = edges[0]
    assert edge.path == "$.child"
    assert edge.target == "CascadeBlanketLeaf"
    assert edge.collection is False
    assert edge.recurse is True
    assert edge.ttl is True
    assert edge.special is True
    assert edge.depth == 2


def test_shape2_collection_of_fk_produces_exactly_one_edge_marked_collection():
    plan = build_cascade_plan([CascadeBookCollection, CascadeAuthor])

    edges = plan["CascadeBookCollection"].fks
    assert len(edges) == 1
    assert edges[0].collection is True
    assert edges[0].target == "CascadeAuthor"
    assert edges[0].path == "$.co_authors"


def test_shape3_nested_submodel_edge_lands_on_holder_and_hides_nested_class():
    plan = build_cascade_plan([CascadeBookNested, CascadeProfile, CascadeAuthor])

    edges = plan["CascadeBookNested"].fks
    assert len(edges) == 1
    assert edges[0].path == "$.profile.mentor"
    assert edges[0].target == "CascadeAuthor"

    # CascadeProfile still gets its own top-level entry (it was passed in
    # `models`) reflecting its OWN field, but is never anyone else's target.
    all_targets = {edge.target for entry in plan.values() for edge in entry.fks}
    assert "CascadeProfile" not in all_targets


def test_depth_key_absent_when_unbounded_never_present_as_none():
    plan = build_cascade_plan([CascadeBookCollection, CascadeAuthor])

    edge = plan["CascadeBookCollection"].fks[0]
    assert edge.depth is None


def test_ttl_is_read_verbatim_from_meta():
    plan = build_cascade_plan([CascadeAuthor])

    assert plan["CascadeAuthor"].ttl == CascadeAuthor.Meta.ttl


def test_special_suffixes_direct_special_field():
    plan = build_cascade_plan([PriorityQueueModel])

    assert plan["PriorityQueueModel"].special_suffixes == ["tasks"]


def test_special_suffixes_nested_inside_contain_sf_submodel():
    plan = build_cascade_plan([PQContainerModel])

    assert plan["PQContainerModel"].special_suffixes == ["inner_pq.tasks"]


def test_build_cascade_plan_over_redis_models_never_uses_none_as_unbounded_signal():
    plan = build_cascade_plan(REDIS_MODELS)

    for entry in plan.values():
        for edge in entry.fks:
            assert edge.depth is None or edge.depth >= 0


def test_every_cascade_fixture_has_the_shared_fixture_ttl_sanity():
    # Every fixture that might root a real cascade-apply
    # invocation — not just cascade TARGETS — must carry a non-None
    # Meta.ttl, or the Lua write phase's `classes[<class>].ttl` lookup for
    # the root's own EXPIRE would resolve to nil (a Lua runtime error).
    for model_cls in CASCADE_PLANNER_MODELS:
        assert model_cls.Meta.ttl == CASCADE_FIXTURE_TTL_SECONDS, model_cls.__name__


@pytest.mark.parametrize(
    "model_cls",
    [
        pytest.param(m, id=m.__name__)
        for m in CASCADE_PLANNER_MODELS
        if m.__name__
        in {"CascadeBookCollection", "CascadeBookNested", "CascadeDiamondRoot"}
    ],
)
def test_flagged_invocation_root_only_fixtures_have_ttl_sanity(model_cls):
    # The three concrete invocation roots will exercise that the
    # TARGET-only validator never required a ttl on (they're roots, never
    # someone else's cascade-enabled target).
    assert model_cls.Meta.ttl == CASCADE_FIXTURE_TTL_SECONDS
