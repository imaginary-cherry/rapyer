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
    CascadeDictCollectionRoot,
    CascadeProfile,
)
from tests.models.special_types import PQContainerModel, PriorityQueueModel
from tests.unit.cascade.conftest import CASCADE_PLANNER_MODELS

pytestmark = pytest.mark.usefixtures("setup_fake_redis_for_cascade_models")


def test_build_cascade_plan_is_importable():
    from rapyer.cascade.planner import build_cascade_plan  # noqa: F401


def test_every_model_gets_exactly_one_entry_even_a_plain_leaf():
    # Act
    plan = build_cascade_plan([CascadeAuthor])

    # Assert - read the ttl off the class; CascadeAuthor carries CASCADE_FIXTURE_TTL_SECONDS.
    assert plan == {
        "CascadeAuthor": CascadePlanEntry(
            ttl=CascadeAuthor.Meta.ttl,
            special_suffixes=[],
            fks=[],
        )
    }


def test_shape1_disabled_field_produces_no_edge():
    # Act
    plan = build_cascade_plan([CascadeBookDirect, CascadeAuthor])

    # Assert
    assert plan["CascadeBookDirect"].fks == []


def test_shape1_blanket_enabled_produces_one_edge_with_global_depth():
    # Act
    plan = build_cascade_plan([CascadeBlanketRoot, CascadeBlanketLeaf])

    # Assert
    edges = plan["CascadeBlanketRoot"].fks
    assert len(edges) == 1
    edge = edges[0]
    assert edge.path == "$.child"
    assert edge.target == "CascadeBlanketLeaf"
    assert edge.is_collection is False
    assert edge.recurse_into_target is True
    assert edge.refresh_target_ttl is True
    assert edge.refresh_target_special_keys is True
    assert edge.depth == 2


def test_shape2_collection_of_fk_produces_exactly_one_edge_marked_collection():
    # Act
    plan = build_cascade_plan([CascadeBookCollection, CascadeAuthor])

    # Assert
    edges = plan["CascadeBookCollection"].fks
    assert len(edges) == 1
    assert edges[0].is_collection is True
    assert edges[0].target == "CascadeAuthor"
    assert edges[0].path == "$.co_authors"


def test_shape2_dict_of_fk_produces_exactly_one_edge_marked_collection():
    # Act
    plan = build_cascade_plan([CascadeDictCollectionRoot, CascadeAuthor])

    # Assert
    edges = plan["CascadeDictCollectionRoot"].fks
    assert len(edges) == 1
    assert edges[0].is_collection is True
    assert edges[0].target == "CascadeAuthor"
    assert edges[0].path == "$.co_authors"


def test_shape3_nested_submodel_edge_lands_on_holder_and_hides_nested_class():
    # Act
    plan = build_cascade_plan([CascadeBookNested, CascadeProfile, CascadeAuthor])

    # Assert
    edges = plan["CascadeBookNested"].fks
    assert len(edges) == 1
    assert edges[0].path == "$.profile.mentor"
    assert edges[0].target == "CascadeAuthor"

    # CascadeProfile gets its own entry for its OWN field but is never anyone else's target.
    all_targets = {edge.target for entry in plan.values() for edge in entry.fks}
    assert "CascadeProfile" not in all_targets


def test_depth_key_absent_when_unbounded_never_present_as_none():
    # Act
    plan = build_cascade_plan([CascadeBookCollection, CascadeAuthor])

    # Assert
    edge = plan["CascadeBookCollection"].fks[0]
    assert edge.depth is None


def test_ttl_is_read_verbatim_from_meta():
    # Act
    plan = build_cascade_plan([CascadeAuthor])

    # Assert
    assert plan["CascadeAuthor"].ttl == CascadeAuthor.Meta.ttl


def test_special_suffixes_direct_special_field():
    # Act
    plan = build_cascade_plan([PriorityQueueModel])

    # Assert
    assert plan["PriorityQueueModel"].special_suffixes == ["tasks"]


def test_special_suffixes_nested_inside_contain_sf_submodel():
    # Act
    plan = build_cascade_plan([PQContainerModel])

    # Assert
    assert plan["PQContainerModel"].special_suffixes == ["inner_pq.tasks"]


def test_build_cascade_plan_over_redis_models_never_uses_none_as_unbounded_signal():
    # Act
    plan = build_cascade_plan(REDIS_MODELS)

    # Assert
    for entry in plan.values():
        for edge in entry.fks:
            assert edge.depth is None or edge.depth >= 0


def test_every_cascade_fixture_has_the_shared_fixture_ttl_sanity():
    # Assert - every possible cascade-apply ROOT needs a non-None Meta.ttl, not just cascade
    # TARGETS, or the Lua write phase's classes[<class>].ttl lookup resolves to nil and errors.
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
    # Assert - these three roots are never anyone else's target, so the old validator skipped them.
    assert model_cls.Meta.ttl == CASCADE_FIXTURE_TTL_SECONDS
