import inspect
from dataclasses import dataclass, field
from types import ModuleType
from typing import Callable

import pytest
from _pytest.reports import TestReport

import rapyer
import rapyer.types  # noqa: F401  # ensure all BaseRedisType subclasses are registered
from rapyer.actions import ACTION_GROUPS_ATTR, ActionGroup
from rapyer.base import AtomicRedisModel
from rapyer.types.base import BaseRedisType
from tests.action_groups import PRIVATE_INHERITED_METHODS, PRIVATE_METHODS

TTL_TESTED_METHODS: set[tuple[str, str]] = set()
TTL_NO_REFRESH_TESTED_METHODS: set[tuple[str, str]] = set()
SPECIAL_FIELD_TESTED_METHODS: set[tuple[str, str, str]] = set()
SPECIAL_FIELD_TTL_TESTED_METHODS: set[tuple[str, str, str]] = set()
BASE_MODEL_TTL_TESTED_METHODS: set[tuple[str, str]] = set()
MODEL_PIPELINE_TESTED_METHODS: set[tuple[str, str]] = set()
STANDALONE_PIPELINE_TESTED_METHODS: set[tuple[str, str]] = set()


def _make_coverage_decorator(coverage_set: set[tuple[str, str]]):
    def coverage_test_for(method: Callable):
        qualname = method.__qualname__
        class_name, method_name = qualname.rsplit(".", 1)

        def decorator(func):
            coverage_set.add((class_name, method_name))
            return func

        return decorator

    return coverage_test_for


ttl_test_for = _make_coverage_decorator(TTL_TESTED_METHODS)
ttl_no_refresh_test_for = _make_coverage_decorator(TTL_NO_REFRESH_TESTED_METHODS)


def _make_special_field_coverage_decorator(coverage_set: set[tuple[str, str, str]]):
    def coverage_test_for(method: Callable, field_type: type):
        qualname = method.__qualname__
        class_name, method_name = qualname.rsplit(".", 1)

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
    if inspect.iscoroutinefunction(obj):
        return True
    wrapped = getattr(obj, "__wrapped__", obj)
    return inspect.isasyncgenfunction(wrapped)


def should_ignore_group(
    method: Callable, ignore_groups: ActionGroup | None = None
) -> bool:
    if ignore_groups is None:
        return False

    groups = getattr(method, ACTION_GROUPS_ATTR, None)
    if groups is None:
        return False
    if groups & ignore_groups:
        return True

    return False


def get_async_methods(cls, ignore_groups: ActionGroup | None = None):
    methods = []
    for name, method in inspect.getmembers(cls, predicate=inspect.iscoroutinefunction):
        if name.startswith("__"):
            continue
        if method.__qualname__.split(".")[0] != cls.__name__:
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
        if getattr(method, "__qualname__", "").split(".")[0] != cls.__name__:
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
        name="cover_pipeline_atom",
        help_text="pipeline atomicity",
        expected=lambda: _collect_methods(ignore_groups=ActionGroup.READ),
    ),
    CoverageCheck(
        name="cover_ttl_refresh",
        help_text="TTL refresh",
        expected=lambda: _collect_methods(only_async=True),
    ),
    CoverageCheck(
        name="cover_ttl_no_refresh",
        help_text="TTL no-refresh",
        expected=lambda: _collect_methods(only_async=True),
    ),
    CoverageCheck(
        name="cover_no_clobber",
        help_text="no-clobber behavior",
        expected=lambda: _collect_methods(),
    ),
]


def pytest_addoption(parser):
    parser.addoption(
        "--skip-pipeline-coverage",
        action="store_true",
        default=False,
        help="Skip the pipeline atomicity coverage check at session end.",
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


def _all_subclasses(cls):
    result = set()
    for sub in cls.__subclasses__():
        result.add(sub)
        result.update(_all_subclasses(sub))
    return result


def _iter_class_methods(cls, async_only: bool):
    members = (
        inspect.getmembers(cls, predicate=inspect.iscoroutinefunction)
        if async_only
        else vars(cls).items()
    )
    for name, method in members:
        if name.startswith("__") or not callable(method):
            continue
        if getattr(method, "__qualname__", "").split(".")[0] != cls.__name__:
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


def _collect_methods(
    ignore_groups: ActionGroup | None = None,
    ignore_private: bool = True,
    only_async: bool = False,
):
    """Callable methods on BaseRedisType subclasses + async methods on AtomicRedisModel.

    When only_async=True, BaseRedisType subclasses are also restricted to async.
    AtomicRedisModel is always async-only since non-async members aren't Redis ops.
    """
    candidates = []
    for cls in _all_subclasses(BaseRedisType):
        candidates.extend(_iter_class_methods(cls, async_only=only_async))
    candidates.extend(_iter_class_methods(AtomicRedisModel, async_only=True))
    candidates.extend(_iter_module_functions(rapyer))

    result = set()
    for holder, name, method in candidates:
        if should_ignore_group(method, ignore_groups):
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
    if session.config.getoption("--skip-pipeline-coverage", default=False):
        return

    has_failures = False
    for check in COVERAGE_CHECKS:
        has_failures |= _emit_coverage_reports(
            session, check.name, check.expected(), check.covered
        )

    if has_failures:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
