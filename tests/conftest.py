import inspect
from typing import Callable

import pytest

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


def get_async_methods(cls):
    methods = []
    for name, method in inspect.getmembers(cls, predicate=inspect.iscoroutinefunction):
        if name.startswith("__"):
            continue
        if method.__qualname__.split(".")[0] != cls.__name__:
            continue
        methods.append((cls.__name__, name))
    return methods


def get_all_type_methods(cls):
    """Discover all callable methods defined directly on cls."""
    methods = []
    for name, method in vars(cls).items():
        if not callable(method):
            continue
        if getattr(method, "__qualname__", "").split(".")[0] != cls.__name__:
            continue
        methods.append((cls.__name__, name))
    return methods


# ── Pipeline atomicity coverage hook ──────────────────────────────────────────

_covered_pipeline_atom_methods: set[tuple[str, str]] = set()


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "cover_pipeline_atom(*methods): marks test as covering pipeline "
        "atomicity for given (class_name, method_name) tuples",
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.outcome != "skipped":
        marker = item.get_closest_marker("cover_pipeline_atom")
        if marker:
            _covered_pipeline_atom_methods.update(marker.args)


def _all_subclasses(cls):
    result = set()
    for sub in cls.__subclasses__():
        result.add(sub)
        result.update(_all_subclasses(sub))
    return result


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    import rapyer.types  # noqa: F401  # ensure all BaseRedisType subclasses are registered

    from rapyer.base import AtomicRedisModel
    from rapyer.types.base import BaseRedisType

    all_methods = set()
    for cls in _all_subclasses(BaseRedisType):
        all_methods.update(get_all_type_methods(cls))
    all_methods.update(get_async_methods(AtomicRedisModel))

    uncovered = sorted(all_methods - _covered_pipeline_atom_methods)
    if uncovered:
        tr = session.config.pluginmanager.get_plugin("terminalreporter")
        if tr:
            tr.section("Pipeline Atomicity Coverage GAPS")
            tr.write_line(
                f"{len(uncovered)} method(s) lack a non-skipped "
                f"pipeline atomicity test:"
            )
            for class_name, method_name in uncovered:
                tr.write_line(f"  - {class_name}.{method_name}")
            tr.write_line("")
            tr.write_line(
                "Add a concrete ActionTestBase subclass with "
                "`covered_method = ClassName.method_name`, "
                "or add an exclusion with justification."
            )
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
