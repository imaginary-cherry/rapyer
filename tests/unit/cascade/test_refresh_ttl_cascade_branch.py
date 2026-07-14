from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest

from rapyer.cascade.planner import build_cascade_plan
from rapyer.scripts.constants import CASCADE_TTL_APPLY_SCRIPT_NAME
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import CascadeAuthor, CascadeChainNode, CascadeChainRoot

# Reused as the "cascade-enabled" fixture (head carries an explicit
# CascadeTTL(depth=2) override) and its target, plus a plain no-FK sibling
# (CascadeAuthor) as the "cascade-disabled" fixture — mirrors the plan's
# instruction to stash `_has_cascade` via the exact same `build_cascade_plan`
# mechanism `init_rapyer()` uses, without invoking `init_rapyer()` itself
# (no real Redis registration is needed for this pure branching test).
_STASH_MODELS = [CascadeChainRoot, CascadeChainNode, CascadeAuthor]


@pytest.fixture(autouse=True)
def stash_has_cascade():
    plan = build_cascade_plan(_STASH_MODELS)
    originals = {model: model._has_cascade for model in _STASH_MODELS}
    for model in _STASH_MODELS:
        model._has_cascade = bool(plan[model.__name__].fks)
    yield
    for model, original in originals.items():
        model._has_cascade = original


@pytest.mark.asyncio
async def test_refresh_ttl_cascade_enabled_model_calls_run_sha_not_expire():
    assert CascadeChainRoot._has_cascade is True
    root = CascadeChainRoot(head="CascadeChainNode:fake")
    mock_pipe = MagicMock()

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta):
        yield mock_pipe

    with (
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_sha") as mock_run_sha,
    ):
        await root.refresh_ttl(can_use_pipeline=True)

    mock_run_sha.assert_called_once_with(
        mock_pipe,
        CASCADE_TTL_APPLY_SCRIPT_NAME,
        1,
        root.key,
        "CascadeChainRoot",
        SPECIAL_FIELD_KEY_PREFIX,
        root.Meta.ttl,
        1,
    )
    mock_pipe.expire.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_ttl_non_cascade_model_also_calls_run_sha():
    # refresh_ttl always routes through the cascade script; a model with no
    # outgoing edges just re-arms its own keys via the script, never expire.
    assert CascadeAuthor._has_cascade is False
    author = CascadeAuthor()
    mock_pipe = MagicMock()

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta):
        yield mock_pipe

    with (
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_sha") as mock_run_sha,
    ):
        await author.refresh_ttl(can_use_pipeline=True)

    mock_run_sha.assert_called_once_with(
        mock_pipe,
        CASCADE_TTL_APPLY_SCRIPT_NAME,
        1,
        author.key,
        "CascadeAuthor",
        SPECIAL_FIELD_KEY_PREFIX,
        author.Meta.ttl,
        1,
    )
    mock_pipe.expire.assert_not_called()
