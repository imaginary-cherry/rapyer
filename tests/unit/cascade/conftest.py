import pytest

from rapyer.types.relational import resolve_relational_targets
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBlanketLeaf,
    CascadeBlanketOptOut,
    CascadeBlanketRoot,
    CascadeBookCollection,
    CascadeBookDirect,
    CascadeBookNested,
    CascadeBookPlain,
    CascadeChainNode,
    CascadeChainRoot,
    CascadeDiamondChild,
    CascadeDiamondRoot,
    CascadeExtendingNode,
    CascadeMultiDepthRoot,
    CascadeProfile,
    CascadeShallowRoot,
)

CASCADE_PLANNER_MODELS = [
    CascadeAuthor,
    CascadeBookDirect,
    CascadeBookCollection,
    CascadeProfile,
    CascadeBookNested,
    CascadeBookPlain,
    CascadeChainNode,
    CascadeChainRoot,
    CascadeExtendingNode,
    CascadeShallowRoot,
    CascadeDiamondChild,
    CascadeDiamondRoot,
    CascadeMultiDepthRoot,
    CascadeBlanketLeaf,
    CascadeBlanketRoot,
    CascadeBlanketOptOut,
]


@pytest.fixture
def setup_fake_redis_for_cascade_models(fake_redis_client):
    original_clients = {}
    for model in CASCADE_PLANNER_MODELS:
        original_clients[model] = (model.Meta.redis, model.Meta.is_fake_redis)
        model.Meta.redis = fake_redis_client
        model.Meta.is_fake_redis = True
    resolve_relational_targets(CASCADE_PLANNER_MODELS)
    yield
    for model, (original_redis, original_is_fake) in original_clients.items():
        model.Meta.redis = original_redis
        model.Meta.is_fake_redis = original_is_fake
