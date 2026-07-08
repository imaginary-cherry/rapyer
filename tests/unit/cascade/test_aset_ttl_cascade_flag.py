import inspect
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rapyer.base import AtomicRedisModel
from rapyer.cascade.planner import build_cascade_plan
from rapyer.result import CascadeResult
from rapyer.scripts.constants import CASCADE_TTL_APPLY_SCRIPT_NAME
from rapyer.types.special import SPECIAL_FIELD_KEY_PREFIX
from tests.models.cascade_types import CascadeAuthor, CascadeChainNode, CascadeChainRoot

TTL_SECONDS = 120

# Same stash mechanism as test_refresh_ttl_cascade_branch.py: reuse
# build_cascade_plan (the exact machinery init_rapyer() uses) rather than
# invoking init_rapyer() itself, since these are pure branching tests that
# need no real Redis registration.
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


def test_aset_ttl_signature_has_cascade_kwarg_defaulting_false():
    sig = inspect.signature(AtomicRedisModel.aset_ttl)
    assert "cascade" in sig.parameters
    assert sig.parameters["cascade"].default is False


@pytest.mark.asyncio
async def test_aset_ttl_no_cascade_flag_on_cascade_enabled_model_never_calls_run_sha():
    # (a) D-03: no flag -> no cascade, even on a _has_cascade=True model.
    assert CascadeChainRoot._has_cascade is True
    root = CascadeChainRoot(head="CascadeChainNode:fake")
    mock_pipe = MagicMock()

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta, should_execute=True):
        yield mock_pipe

    with (
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_sha") as mock_run_sha,
    ):
        result = await root.aset_ttl(TTL_SECONDS)

    assert result is None
    mock_run_sha.assert_not_called()
    mock_pipe.expire.assert_called_once_with(root.key, TTL_SECONDS)


@pytest.mark.asyncio
async def test_aset_ttl_cascade_flag_on_non_cascade_model_never_calls_run_sha():
    # (b) D-03: the flag is a gate over pre-configured edges, never an
    # override -- a _has_cascade=False model stays on the legacy path even
    # with cascade=True.
    assert CascadeAuthor._has_cascade is False
    author = CascadeAuthor()
    mock_pipe = MagicMock()

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta, should_execute=True):
        yield mock_pipe

    with (
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_sha") as mock_run_sha,
    ):
        result = await author.aset_ttl(TTL_SECONDS, cascade=True)

    assert result is None
    mock_run_sha.assert_not_called()
    mock_pipe.expire.assert_called_once_with(author.key, TTL_SECONDS)


@pytest.mark.asyncio
async def test_aset_ttl_cascade_standalone_owns_execution_and_returns_cascade_result():
    # (c) standalone call (no outer pipeline): enqueues run_sha, awaits
    # pipe.execute() itself, and decodes the two-element result.
    assert CascadeChainRoot._has_cascade is True
    root = CascadeChainRoot(head="CascadeChainNode:fake")
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[True, [1, 2]])

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta, should_execute=True):
        yield mock_pipe

    with (
        patch("rapyer.base._context_pipe") as mock_context_pipe,
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_sha") as mock_run_sha,
    ):
        mock_context_pipe.get.return_value = None
        result = await root.aset_ttl(TTL_SECONDS, cascade=True)

    mock_run_sha.assert_called_once_with(
        mock_pipe,
        CASCADE_TTL_APPLY_SCRIPT_NAME,
        1,
        root.key,
        "CascadeChainRoot",
        SPECIAL_FIELD_KEY_PREFIX,
        TTL_SECONDS,
    )
    mock_pipe.execute.assert_awaited_once()
    assert result == CascadeResult(dangling_children=1, dangling_special=2)


@pytest.mark.asyncio
async def test_aset_ttl_cascade_inside_outer_pipeline_returns_none_without_executing():
    # (d) called while already inside an outer pipeline: enqueues into the
    # outer pipe, never calls pipe.execute() itself, returns None.
    assert CascadeChainRoot._has_cascade is True
    root = CascadeChainRoot(head="CascadeChainNode:fake")
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock()

    @asynccontextmanager
    async def fake_ensure_pipeline(_meta, should_execute=True):
        yield mock_pipe

    with (
        patch("rapyer.base._context_pipe") as mock_context_pipe,
        patch("rapyer.base.ensure_pipeline", fake_ensure_pipeline),
        patch("rapyer.base.scripts_registry.run_sha") as mock_run_sha,
    ):
        mock_context_pipe.get.return_value = mock_pipe
        result = await root.aset_ttl(TTL_SECONDS, cascade=True)

    mock_run_sha.assert_called_once()
    mock_pipe.execute.assert_not_awaited()
    assert result is None
