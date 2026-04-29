from typing import Any, ClassVar

import pytest

from rapyer import AtomicRedisModel
from rapyer.actions import ActionGroup

BENCHMARK_TTL_SECONDS = 3600


class AsyncBenchmarkTest:
    pytestmark = [pytest.mark.benchmark]
    rounds = 20
    expected = None

    async def setup(self) -> Any:
        return None

    async def action(self, *args, **kwargs) -> Any:
        raise NotImplementedError()

    def _run(self, benchmark, event_loop):
        def sync_setup():
            result = event_loop.run_until_complete(self.setup())
            if result is None:
                return (), {}
            return (result,), {}

        def sync_action(*args, **kwargs):
            return event_loop.run_until_complete(self.action(*args, **kwargs))

        result = benchmark.pedantic(sync_action, setup=sync_setup, rounds=self.rounds)

        if self.expected is not None:
            assert result == self.expected

    def test_benchmark(self, benchmark, event_loop):
        self._run(benchmark, event_loop)


class AsyncBenchmarkTestWithTTL(AsyncBenchmarkTest):
    models_for_ttl: ClassVar[tuple[AtomicRedisModel, ...]] = ()

    def test_benchmark_with_ttl(self, benchmark, event_loop):
        original = [
            (cls, cls.Meta.ttl, cls.Meta.refresh_ttl) for cls in self.models_for_ttl
        ]
        for cls in self.models_for_ttl:
            cls.Meta.ttl = BENCHMARK_TTL_SECONDS
            cls.Meta.refresh_ttl = ActionGroup.all(for_ttl=True)
            cls.model_rebuild(force=True)
        try:
            self._run(benchmark, event_loop)
        finally:
            for cls, ttl, original_refresh in original:
                cls.Meta.ttl = ttl
                cls.Meta.refresh_ttl = original_refresh
                cls.model_rebuild(force=True)
