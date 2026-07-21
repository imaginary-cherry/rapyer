from benchmarks.base import AsyncBenchmarkTest, TTLMode
from benchmarks.models import (
    BENCHMARK_CASCADE_DEPTH,
    BENCHMARK_CASCADE_LIST_SIZE,
    BENCHMARK_TTL_SECONDS,
    BenchCascadeChainNode,
    BenchCascadeChild,
    BenchCascadeListRoot,
    BenchCascadeTwoFkRoot,
)


class TestCascadeTtlTwoForeignKeys(AsyncBenchmarkTest):
    """Cascade TTL across a root with two direct FK children."""

    models = {TTLMode.NO_TTL: BenchCascadeTwoFkRoot}

    async def setup(self, mode):
        cls = self.models[mode]
        first = BenchCascadeChild(name="first")
        second = BenchCascadeChild(name="second")
        await first.asave()
        await second.asave()
        root = cls(name="root", first=first.key, second=second.key)
        await root.asave()
        return root

    async def action(self, root):
        return await root.aset_ttl(BENCHMARK_TTL_SECONDS, cascade=True)


class TestCascadeTtlDeepChain(AsyncBenchmarkTest):
    """Cascade TTL down a linear FK chain ``BENCHMARK_CASCADE_DEPTH`` layers deep."""

    models = {TTLMode.NO_TTL: BenchCascadeChainNode}

    async def setup(self, mode):
        cls = self.models[mode]
        # Build tail-first so each node references an already-persisted child.
        node = cls(name="node-0")
        await node.asave()
        for i in range(1, BENCHMARK_CASCADE_DEPTH):
            node = cls(name=f"node-{i}", next=node.key)
            await node.asave()
        return node

    async def action(self, head):
        return await head.aset_ttl(BENCHMARK_TTL_SECONDS, cascade=True)


class TestCascadeTtlListOfForeignKeys(AsyncBenchmarkTest):
    """Cascade TTL across a root holding a list of ``BENCHMARK_CASCADE_LIST_SIZE`` FKs."""

    models = {TTLMode.NO_TTL: BenchCascadeListRoot}

    async def setup(self, mode):
        cls = self.models[mode]
        children = [
            BenchCascadeChild(name=f"child-{i}")
            for i in range(BENCHMARK_CASCADE_LIST_SIZE)
        ]
        for child in children:
            await child.asave()
        root = cls(name="root", children=[child.key for child in children])
        await root.asave()
        return root

    async def action(self, root):
        return await root.aset_ttl(BENCHMARK_TTL_SECONDS, cascade=True)
