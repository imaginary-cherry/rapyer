from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest

from rapyer.actions import ActionGroup
from tests.models.simple_types import TTLRefreshTestModel


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["refresh_ttl", "action", "expected_refresh"],
    [
        pytest.param(True, ActionGroup.READ, True, id="bool-true-read"),
        pytest.param(True, ActionGroup.DELETE, True, id="bool-true-delete"),
        pytest.param(False, ActionGroup.READ, False, id="bool-false-read"),
        pytest.param(False, ActionGroup.UPDATE, False, id="bool-false-update"),
        pytest.param(ActionGroup.READ, ActionGroup.READ, True, id="single-read-read"),
        pytest.param(
            ActionGroup.READ, ActionGroup.UPDATE, False, id="single-read-vs-update"
        ),
        pytest.param(
            ActionGroup.UPDATE, ActionGroup.UPDATE, True, id="single-update-update"
        ),
        pytest.param(
            ActionGroup.UPDATE, ActionGroup.DELETE, False, id="single-update-vs-delete"
        ),
        pytest.param(
            ActionGroup.APPEND, ActionGroup.APPEND, True, id="single-append-append"
        ),
        pytest.param(
            ActionGroup.ERASE, ActionGroup.ERASE, True, id="single-erase-erase"
        ),
        pytest.param(
            ActionGroup.FETCH, ActionGroup.FETCH, True, id="single-fetch-fetch"
        ),
        pytest.param(
            ActionGroup.ARITHMETIC,
            ActionGroup.ARITHMETIC,
            True,
            id="single-arithmetic-arithmetic",
        ),
        pytest.param(
            ActionGroup.READ | ActionGroup.UPDATE,
            ActionGroup.READ,
            True,
            id="two-ru-read",
        ),
        pytest.param(
            ActionGroup.READ | ActionGroup.UPDATE,
            ActionGroup.UPDATE,
            True,
            id="two-ru-update",
        ),
        pytest.param(
            ActionGroup.READ | ActionGroup.UPDATE,
            ActionGroup.DELETE,
            False,
            id="two-ru-vs-delete",
        ),
        pytest.param(
            ActionGroup.READ | ActionGroup.UPDATE,
            ActionGroup.APPEND,
            False,
            id="two-ru-vs-append",
        ),
        pytest.param(
            ActionGroup.READ,
            ActionGroup.UPDATE | ActionGroup.APPEND,
            False,
            id="multi-action-no-overlap",
        ),
        pytest.param(
            ActionGroup.UPDATE,
            ActionGroup.UPDATE | ActionGroup.APPEND,
            True,
            id="multi-action-overlap-update",
        ),
        pytest.param(
            ActionGroup.APPEND,
            ActionGroup.UPDATE | ActionGroup.APPEND,
            True,
            id="multi-action-overlap-append",
        ),
        pytest.param(
            ActionGroup.all(for_ttl=True), ActionGroup.READ, True, id="all-read"
        ),
        pytest.param(
            ActionGroup.all(for_ttl=True),
            ActionGroup.ARITHMETIC,
            True,
            id="all-arithmetic",
        ),
    ],
)
async def test_refresh_ttl_if_needed_honors_action_groups(
    monkeypatch, refresh_ttl, action, expected_refresh
):
    monkeypatch.setattr(TTLRefreshTestModel.Meta, "refresh_ttl", refresh_ttl)

    mock_pipe = MagicMock()

    @asynccontextmanager
    async def fake_pipeline(_meta):
        yield mock_pipe

    model = TTLRefreshTestModel(name="action-matrix")

    # refresh_ttl always routes through the cascade script, so a refresh shows up
    # as a run_sha call rather than a pipe.expire.
    with (
        patch("rapyer.base.pipeline_with_execution", fake_pipeline),
        patch("rapyer.base.scripts_registry.run_sha") as mock_run_sha,
    ):
        await model.refresh_ttl_if_needed(action=action)

    assert mock_run_sha.called is expected_refresh, (
        f"refresh_ttl={refresh_ttl!r} action={action!r}: "
        f"expected run_sha.called={expected_refresh}, "
        f"got call_count={mock_run_sha.call_count}"
    )


def test_should_refresh_classmethod_returns_bool():
    # Coverage: the should_refresh() classmethod (a thin wrapper over
    # should_refresh_for_action that nothing else exercised).
    # Act / Assert
    assert isinstance(TTLRefreshTestModel.should_refresh(), bool)
