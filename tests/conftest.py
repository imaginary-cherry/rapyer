import inspect
from dataclasses import dataclass, field
from types import ModuleType
from typing import Callable
from unittest.mock import AsyncMock

import pytest
from _pytest.reports import TestReport

import rapyer
import rapyer.types  # noqa: F401  # ensure all BaseRedisType subclasses are registered
from rapyer.actions import ACTION_GROUPS_ATTR, ActionGroup
from rapyer.base import AtomicRedisModel
from rapyer.types.base import BaseRedisType
from rapyer.types.special import SpecialFieldType
from tests.action_groups import (
    NON_ACTION_METHODS,
    PRIVATE_INHERITED_METHODS,
    PRIVATE_METHODS,
)
from tests.coverage_helpers import (
    COVER_NO_CLOBBER,
    COVER_NO_TTL_WHEN_NOT_CONFIGURED,
    COVER_PIPELINE_ATOM,
    COVER_TTL_NO_REFRESH,
    COVER_TTL_REFRESH,
    COVER_TTL_UPDATE_ONCE,
    SPECIAL_FIELD_LIFECYCLE,
    SPECIAL_FIELD_TTL_REFRESH,
    all_subclasses,
    cover_tuple,
    should_ignore_group,
    special_field_cover_marker,
)

TTL_TESTED_METHODS: set[tuple[str, str]] = set()
TTL_NO_REFRESH_TESTED_METHODS: set[tuple[str, str]] = set()
SPECIAL_FIELD_TESTED_METHODS: set[tuple[str, str, str]] = set()
SPECIAL_FIELD_TTL_TESTED_METHODS: set[tuple[str, str, str]] = set()
BASE_MODEL_TTL_TESTED_METHODS: set[tuple[str, str]] = set()
MODEL_PIPELINE_TESTED_METHODS: set[tuple[str, str]] = set()
STANDALONE_PIPELINE_TESTED_METHODS: set[tuple[str, str]] = set()


@pytest.fixture
def force_no_ttl_updates(monkeypatch):
    flush_mock = AsyncMock()
    monkeypatch.setattr(rapyer.actions, "flush_action_targets", flush_mock)
    return flush_mock


def _make_coverage_decorator(coverage_set: set[tuple[str, str]]):
    def coverage_test_for(method: Callable):
        class_name, method_name = cover_tuple(method)

        def decorator(func):
            coverage_set.add((class_name, method_name))
            return func

        return decorator

    return coverage_test_for


ttl_test_for = _make_coverage_decorator(TTL_TESTED_METHODS)
ttl_no_refresh_test_for = _make_coverage_decorator(TTL_NO_REFRESH_TESTED_METHODS)


def _make_special_field_coverage_decorator(coverage_set: set[tuple[str, str, str]]):
    def coverage_test_for(method: Callable, field_type: type):
        class_name, method_name = cover_tuple(method)

        def decorator(func):
            coverage_set.add((class_name, method_name, field_type.__name__))
            return func

        return decorator

    return coverage_test_for


special_field_test_for = _make_special_field_coverage_decorator(
    SPECIAL_FIELD_TESTED_METHODS
)
special_field_ttl_test_for = _make_special_field_coverage_decorator(
    SPECIAL_FIELD_TTL_TESTED_METHODS
)
base_model_ttl_test_for = _make_coverage_decorator(BASE_MODEL_TTL_TESTED_METHODS)
model_pipeline_test_for = _make_coverage_decorator(MODEL_PIPELINE_TESTED_METHODS)
standalone_pipeline_test_for = _make_coverage_decorator(
    STANDALONE_PIPELINE_TESTED_METHODS
)


def _is_async_callable(obj) -> bool:
    if inspect.iscoroutinefunction(obj) or inspect.isasyncgenfunction(obj):
        return True
    wrapped = getattr(obj, "__wrapped__", obj)
    return inspect.iscoroutinefunction(wrapped) or inspect.isasyncgenfunction(wrapped)


def get_async_methods(cls, ignore_groups: ActionGroup | None = None):
    methods = []
    for name, method in inspect.getmembers(cls, predicate=inspect.iscoroutinefunction):
        if name.startswith("__"):
            continue
        if cover_tuple(method)[0] != cls.__name__:
            continue
        if should_ignore_group(method, ignore_groups):
            continue
        methods.append((cls.__name__, name))
    return methods


def get_all_type_methods(cls, ignore_groups: ActionGroup | None = None):
    """Discover all callable methods defined directly on cls."""
    methods = []
    for name, method in vars(cls).items():
        if not callable(method):
            continue
        if cover_tuple(method)[0] != cls.__name__:
            continue
        if should_ignore_group(method, ignore_groups):
            continue
        methods.append((cls.__name__, name))
    return methods


def get_module_level_functions(module):
    """Collect public module-level functions listed in the module's __all__."""
    functions = []
    for name in getattr(module, "__all__", []):
        obj = getattr(module, name, None)
        if obj is None or inspect.isclass(obj) or not callable(obj):
            continue
        functions.append((rapyer.__name__, name))
    return functions


# ── Pipeline atomicity coverage hook ──────────────────────────────────────────


@dataclass(frozen=True)
class CoverageCheck:
    name: str
    help_text: str
    expected: Callable[[], set[tuple[str, str]]]
    covered: set[tuple[str, str]] = field(default_factory=set)


COVERAGE_CHECKS: list[CoverageCheck] = [
    CoverageCheck(
        name=COVER_PIPELINE_ATOM,
        help_text="pipeline atomicity",
        expected=lambda: _collect_methods(ignore_groups=ActionGroup.READ),
    ),
    CoverageCheck(
        name=COVER_TTL_REFRESH,
        help_text="TTL refresh",
        expected=lambda: _collect_methods(
            only_async=True, ignore_groups=ActionGroup.DELETE
        ),
    ),
    CoverageCheck(
        name=COVER_TTL_NO_REFRESH,
        help_text="TTL no-refresh",
        expected=lambda: _collect_methods(
            only_async=True, ignore_groups=ActionGroup.DELETE | ActionGroup.CREATE
        ),
    ),
    CoverageCheck(
        name=COVER_TTL_UPDATE_ONCE,
        help_text="TTL Update once",
        expected=lambda: _collect_methods(
            only_async=True, ignore_groups=ActionGroup.DELETE | ActionGroup.CREATE
        ),
    ),
    CoverageCheck(
        name=COVER_NO_CLOBBER,
        help_text="no-clobber behavior",
        expected=lambda: _collect_methods(
            # Delete and create effect the entire model
            ignore_groups=(ActionGroup.DELETE | ActionGroup.CREATE)
        ),
    ),
    CoverageCheck(
        name=COVER_NO_TTL_WHEN_NOT_CONFIGURED,
        help_text="No TTL set when ttl is not configured",
        expected=lambda: _collect_methods(
            only_async=True, require_groups=ActionGroup.CREATE
        ),
    ),
]

for sf_class in all_subclasses(SpecialFieldType):
    sf_class: type[SpecialFieldType]
    COVERAGE_CHECKS.extend(
        [
            CoverageCheck(
                name=special_field_cover_marker(sf_class, SPECIAL_FIELD_LIFECYCLE),
                help_text=f"{sf_class.__name__} special field lifecycle",
                expected=lambda: _collect_methods(
                    only_async=True,
                    require_groups=ActionGroup.CREATE | ActionGroup.DELETE,
                ),
            ),
            CoverageCheck(
                name=special_field_cover_marker(sf_class, SPECIAL_FIELD_TTL_REFRESH),
                help_text=f"{sf_class.__name__} special field TTL refresh",
                expected=lambda: _collect_methods(
                    # Delete and create effect the entire model
                    ignore_groups=(ActionGroup.DELETE | ActionGroup.CREATE),
                    include_redis_types=False,
                ),
            ),
        ]
    )
COVERAGE_FLAG = "action-coverage"


def pytest_addoption(parser):
    parser.addoption(
        f"--{COVERAGE_FLAG}",
        action="store_true",
        default=False,
        help="Run the action coverage check at session end.",
    )


def pytest_configure(config):
    for check in COVERAGE_CHECKS:
        config.addinivalue_line(
            "markers",
            f"{check.name}(*methods): marks test as covering "
            f"{check.help_text} for given (class_name, method_name) tuples",
        )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.outcome != "skipped":
        for check in COVERAGE_CHECKS:
            marker = item.get_closest_marker(check.name)
            if marker:
                check.covered.update(marker.args)


def _iter_class_methods(cls, async_only: bool):
    members = (
        inspect.getmembers(cls, predicate=_is_async_callable)
        if async_only
        else vars(cls).items()
    )
    for name, method in members:
        if isinstance(method, (classmethod, staticmethod)):
            method = method.__func__
        if name.startswith("__") or not callable(method):
            continue
        if cover_tuple(method)[0] != cls.__name__:
            continue
        yield cls, name, method


def _iter_module_functions(module: ModuleType):
    for name in getattr(module, "__all__", []):
        obj = getattr(module, name, None)
        if obj is None or inspect.isclass(obj) or not callable(obj):
            continue
        yield module, name, obj


def _is_private_method(holder, method_name: str) -> bool:
    """Private if (holder, method_name) is an exact match in PRIVATE_METHODS,
    or if any ancestor class lists method_name in PRIVATE_INHERITED_METHODS."""
    if (holder.__name__, method_name) in PRIVATE_METHODS:
        return True
    if inspect.isclass(holder):
        return any(
            (ancestor.__name__, method_name) in PRIVATE_INHERITED_METHODS
            for ancestor in holder.__mro__
        )
    return False


def _is_non_action(holder, method_name: str) -> bool:
    return (holder.__name__, method_name) in NON_ACTION_METHODS


def _collect_methods(
    ignore_groups: ActionGroup | None = None,
    require_groups: ActionGroup | None = None,
    ignore_private: bool = True,
    only_async: bool = False,
    include_redis_types: bool = True,
):
    """Callable methods on BaseRedisType subclasses + async methods on AtomicRedisModel.

    When only_async=True, BaseRedisType subclasses are also restricted to async.
    AtomicRedisModel is always async-only since non-async members aren't Redis ops.
    When require_groups is set, only methods tagged with at least one of those
    action groups are included.
    """
    candidates = []
    if include_redis_types:
        for cls in all_subclasses(BaseRedisType):
            candidates.extend(_iter_class_methods(cls, async_only=only_async))
    candidates.extend(_iter_class_methods(AtomicRedisModel, async_only=only_async))
    candidates.extend(_iter_module_functions(rapyer))

    result = set()
    for holder, name, method in candidates:
        if should_ignore_group(method, ignore_groups):
            continue
        if require_groups is not None:
            groups = getattr(method, ACTION_GROUPS_ATTR, None)
            if groups is None or not (groups & require_groups):
                continue
        if _is_non_action(holder, name):
            continue
        if ignore_private and _is_private_method(holder, name):
            continue
        result.add((holder.__name__, name))
    return result


def _emit_coverage_reports(session, check_name, expected, covered):
    uncovered = sorted(expected - covered)
    for class_name, method_name in uncovered:
        report = TestReport(
            nodeid=f"{check_name}::{class_name}.{method_name}",
            location=(check_name, 0, f"{class_name}.{method_name}"),
            keywords={check_name: True},
            outcome="failed",
            longrepr=(
                f"{class_name}.{method_name} lacks a non-skipped "
                f"{check_name} test.\n"
                f"Add a concrete ActionTestBase subclass with "
                f"`covered_method = {class_name}.{method_name}`, "
                f"or add an exclusion with justification."
            ),
            when="call",
        )
        session.config.hook.pytest_runtest_logreport(report=report)

    for class_name, method_name in sorted(expected & covered):
        report = TestReport(
            nodeid=f"{check_name}::{class_name}.{method_name}",
            location=(check_name, 0, f"{class_name}.{method_name}"),
            keywords={check_name: True},
            outcome="passed",
            longrepr=None,
            when="call",
        )
        session.config.hook.pytest_runtest_logreport(report=report)

    return len(uncovered) > 0


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption(f"--{COVERAGE_FLAG}", default=False):
        return

    has_failures = False
    for check in COVERAGE_CHECKS:
        has_failures |= _emit_coverage_reports(
            session, check.name, check.expected(), check.covered
        )

    if has_failures:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
