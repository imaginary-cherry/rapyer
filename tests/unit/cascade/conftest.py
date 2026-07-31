from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

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
    CascadeDictCollectionRoot,
    CascadeExtendingNode,
    CascadeMaxBudgetRoot,
    CascadeMultiDepthRoot,
    CascadeNestedDepthRoot,
    CascadePQRefParent,
    CascadeProfile,
    CascadeSetRefBlanket,
    CascadeSetRefOptOut,
    CascadeSetRefParent,
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
    CascadeDictCollectionRoot,
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
    CascadeSetRefParent,
    CascadePQRefParent,
    CascadeSetRefBlanket,
    CascadeSetRefOptOut,
]

# init_rapyer() authoritatively resets Meta.cascade_ttl to None on every registered
# model (see test_init_rapyer_cascade_ttl.py). Snapshotting here, at conftest import
# time, captures each class's declared value before any test can call init_rapyer().
_DECLARED_CASCADE_TTL = {
    model: model.Meta.cascade_ttl for model in CASCADE_PLANNER_MODELS
}


@pytest.fixture
def setup_fake_redis_for_cascade_models(fake_redis_client):
    original_clients = {}
    for model in CASCADE_PLANNER_MODELS:
        original_clients[model] = (
            model.Meta.redis,
            model.Meta.is_fake_redis,
            model.Meta.cascade_ttl,
        )
        model.Meta.redis = fake_redis_client
        model.Meta.is_fake_redis = True
        model.Meta.cascade_ttl = _DECLARED_CASCADE_TTL[model]
    resolve_relational_targets(CASCADE_PLANNER_MODELS)
    yield
    for model, (
        original_redis,
        original_is_fake,
        original_cascade_ttl,
    ) in original_clients.items():
        model.Meta.redis = original_redis
        model.Meta.is_fake_redis = original_is_fake
        model.Meta.cascade_ttl = original_cascade_ttl


@pytest.fixture
def fcall_pipeline_spy():
    """Patches ensure_pipeline + scripts_registry.run_fcall so a refresh_ttl()/
    aset_ttl() call can be asserted against the FCALL args without touching real
    Redis. Accepts the optional should_execute kwarg aset_ttl's call site passes.
    Yields (mock_pipe, mock_run_fcall)."""
    mock_pipe = MagicMock()

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta, should_execute=True):
        yield mock_pipe

    with (
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_fcall") as mock_run_fcall,
    ):
        yield mock_pipe, mock_run_fcall


@pytest_asyncio.fixture
async def setup_fake_redis_for_cascade_apply(fake_redis_client):
    """
    Wire every CASCADE_PLANNER_MODELS class onto fakeredis for the root-own-keys
    EXPIRE fallback tests. Cascade traversal is real-Redis-only, so no cascade
    function is loaded here.
    """
    original_clients = {}
    for model in CASCADE_PLANNER_MODELS:
        original_clients[model] = (
            model.Meta.redis,
            model.Meta.is_fake_redis,
            model.Meta.cascade_ttl,
        )
        model.Meta.redis = fake_redis_client
        model.Meta.is_fake_redis = True
        model.Meta.cascade_ttl = _DECLARED_CASCADE_TTL[model]
    resolve_relational_targets(CASCADE_PLANNER_MODELS)
    await register_scripts(fake_redis_client, is_fakeredis=True)
    yield
    for model, (
        original_redis,
        original_is_fake,
        original_cascade_ttl,
    ) in original_clients.items():
        model.Meta.redis = original_redis
        model.Meta.is_fake_redis = original_is_fake
        model.Meta.cascade_ttl = original_cascade_ttl
