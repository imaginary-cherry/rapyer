import inspect
from typing import Callable

import pytest
from _pytest.reports import TestReport

import rapyer.types  # noqa: F401  # ensure all BaseRedisType subclasses are registered
from rapyer.actions import ACTION_GROUPS_ATTR, ActionGroup
from rapyer.base import AtomicRedisModel
from rapyer.types.base import BaseRedisType

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

def should_ignore_group(method: Callable, ignore_groups: ActionGroup | None = None) ->bool:
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


# ── Pipeline atomicity coverage hook ──────────────────────────────────────────

_covered_pipeline_atom_methods: set[tuple[str, str]] = set()
_covered_ttl_refresh_methods: set[tuple[str, str]] = set()
_covered_ttl_no_refresh_methods: set[tuple[str, str]] = set()
_covered_no_clobber_methods: set[tuple[str, str]] = set()


def pytest_addoption(parser):
    parser.addoption(
        "--skip-pipeline-coverage",
        action="store_true",
        default=False,
        help="Skip the pipeline atomicity coverage check at session end.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "cover_pipeline_atom(*methods): marks test as covering pipeline "
        "atomicity for given (class_name, method_name) tuples",
    )
    config.addinivalue_line(
        "markers",
        "cover_ttl_refresh(*methods): marks test as covering TTL refresh "
        "for given (class_name, method_name) tuples",
    )
    config.addinivalue_line(
        "markers",
        "cover_ttl_no_refresh(*methods): marks test as covering TTL "
        "no-refresh for given (class_name, method_name) tuples",
    )
    config.addinivalue_line(
        "markers",
        "cover_no_clobber(*methods): marks test as covering no-clobber "
        "behavior for given (class_name, method_name) tuples",
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.outcome != "skipped":
        for mark_name, coverage_set in (
            ("cover_pipeline_atom", _covered_pipeline_atom_methods),
            ("cover_ttl_refresh", _covered_ttl_refresh_methods),
            ("cover_ttl_no_refresh", _covered_ttl_no_refresh_methods),
            ("cover_no_clobber", _covered_no_clobber_methods),
        ):
            marker = item.get_closest_marker(mark_name)
            if marker:
                coverage_set.update(marker.args)


def _all_subclasses(cls):
    result = set()
    for sub in cls.__subclasses__():
        result.add(sub)
        result.update(_all_subclasses(sub))
    return result


def _collect_all_methods(ignore_groups: ActionGroup | None = None):
    """All callable methods on BaseRedisType subclasses + async methods on AtomicRedisModel."""
    all_methods = set()
    for cls in _all_subclasses(BaseRedisType):
        all_methods.update(get_all_type_methods(cls, ignore_groups=ignore_groups))
    all_methods.update(get_async_methods(AtomicRedisModel, ignore_groups=ignore_groups))
    return all_methods


def _collect_async_methods(ignore_groups: ActionGroup | None = None):
    """Async methods on BaseRedisType subclasses + AtomicRedisModel."""
    all_methods = set()
    for cls in _all_subclasses(BaseRedisType):
        all_methods.update(get_async_methods(cls, ignore_groups=ignore_groups))
    all_methods.update(get_async_methods(AtomicRedisModel, ignore_groups=ignore_groups))
    return all_methods


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

    # Pipeline atomicity: all methods (sync + async)
    all_methods = _collect_all_methods()
    has_failures |= _emit_coverage_reports(
        session,
        "cover_pipeline_atom",
        all_methods,
        _covered_pipeline_atom_methods,
    )

    # TTL refresh / no-refresh: async methods only
    async_methods = _collect_async_methods()
    has_failures |= _emit_coverage_reports(
        session,
        "cover_ttl_refresh",
        async_methods,
        _covered_ttl_refresh_methods,
    )
    has_failures |= _emit_coverage_reports(
        session,
        "cover_ttl_no_refresh",
        async_methods,
        _covered_ttl_no_refresh_methods,
    )

    # No-clobber: all methods (sync + async)
    has_failures |= _emit_coverage_reports(
        session,
        "cover_no_clobber",
        all_methods,
        _covered_no_clobber_methods,
    )

    if has_failures:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
