import pytest
import pytest_asyncio

from rapyer.scripts import register_scripts
from rapyer.types.relational import resolve_relational_targets
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBlanketCollectionRoot,
    CascadeBlanketLeaf,
    CascadeBlanketNestedHolder,
    CascadeBlanketNestedProfile,
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
    CascadeMaxBudgetRoot,
    CascadeMultiDepthRoot,
    CascadeNestedDepthRoot,
    CascadeProfile,
    CascadeShallowRoot,
    CascadeSpecialChild,
    CascadeSpecialParent,
    CascadeWR02Grandchild,
    CascadeWR02Root,
    CascadeWR02SharedChild,
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
    CascadeBlanketCollectionRoot,
    CascadeBlanketNestedProfile,
    CascadeBlanketNestedHolder,
    CascadeNestedDepthRoot,
    CascadeSpecialChild,
    CascadeSpecialParent,
    CascadeWR02Grandchild,
    CascadeWR02SharedChild,
    CascadeWR02Root,
    CascadeMaxBudgetRoot,
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


@pytest_asyncio.fixture
async def setup_fake_redis_for_cascade_apply(fake_redis_client):
    """
    Same wiring as ``setup_fake_redis_for_cascade_models``, plus a real
    ``register_scripts`` call so the registered ``cascade_ttl_apply`` SHA's
    baked-in plan table reflects every ``CASCADE_PLANNER_MODELS`` class
    (``fake_redis_client`` itself already registered scripts once at fixture
    creation time, before these classes' ``Meta.redis`` was wired here).
    """
    original_clients = {}
    for model in CASCADE_PLANNER_MODELS:
        original_clients[model] = (model.Meta.redis, model.Meta.is_fake_redis)
        model.Meta.redis = fake_redis_client
        model.Meta.is_fake_redis = True
    resolve_relational_targets(CASCADE_PLANNER_MODELS)
    await register_scripts(fake_redis_client, is_fakeredis=True)
    yield
    for model, (original_redis, original_is_fake) in original_clients.items():
        model.Meta.redis = original_redis
        model.Meta.is_fake_redis = original_is_fake
