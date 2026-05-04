import enum
from typing import Any, ClassVar

import pytest

from rapyer import AtomicRedisModel


class TTLMode(enum.Enum):
    """Which model variant a benchmark iteration is exercising.

    Each test class declares a ``models`` mapping from this enum to the model
    class it should construct in setup. The TTL variant is a separate, pristine
    subclass with TTL configured at class-definition time — no Meta mutation,
    no install/uninstall cycles between benchmarks.
    """

    NO_TTL = "no_ttl"
    TTL = "ttl"


class AsyncBenchmarkTest:
    pytestmark = [pytest.mark.benchmark]
    rounds = 20
    expected = None

    # Subclasses override. ``TTLMode.NO_TTL`` is required (used by
    # ``test_benchmark``); ``TTLMode.TTL`` is required by subclasses that also
    # run ``test_benchmark_with_ttl``.
    models: ClassVar[dict[TTLMode, type[AtomicRedisModel]]] = {}

    async def setup(self, mode: TTLMode) -> Any:
        return None

    async def action(self, *args, **kwargs) -> Any:
        raise NotImplementedError()

    def _run(self, benchmark, event_loop, mode: TTLMode):
        def sync_setup():
            result = event_loop.run_until_complete(self.setup(mode))
            if result is None:
                return (), {}
            return (result,), {}

        def sync_action(*args, **kwargs):
            return event_loop.run_until_complete(self.action(*args, **kwargs))

        result = benchmark.pedantic(sync_action, setup=sync_setup, rounds=self.rounds)

        if self.expected is not None:
            assert result == self.expected

    def test_benchmark(self, benchmark, event_loop):
        self._run(benchmark, event_loop, TTLMode.NO_TTL)


class AsyncBenchmarkTestWithTTL(AsyncBenchmarkTest):
    def test_benchmark_with_ttl(self, benchmark, event_loop):
        self._run(benchmark, event_loop, TTLMode.TTL)
