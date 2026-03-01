from typing import Any

import pytest


class AsyncBenchmarkTest:
    pytestmark = [pytest.mark.benchmark]
    rounds = 20
    expected = None

    async def setup(self) -> Any:
        return None

    async def action(self, *args, **kwargs) -> Any:
        raise NotImplementedError()

    def test_benchmark(self, benchmark, event_loop):
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
