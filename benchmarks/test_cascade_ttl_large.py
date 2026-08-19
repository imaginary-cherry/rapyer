import math
from typing import Any

from benchmarks.base import AsyncBenchmarkTest, TTLMode
from benchmarks.models import (
    BENCHMARK_CASCADE_LARGE_BRANCH,
    BENCHMARK_CASCADE_LARGE_SIZE,
    BENCHMARK_TTL_SECONDS,
    BenchCascadeLargeChainNode,
    BenchCascadeLargeFanRoot,
    BenchCascadeLargeLeaf,
    BenchCascadeLargeTreeNode,
)
from rapyer.base import AtomicRedisModel

INSERT_BATCH = 10_000
# branch**depth == size, so 1,000,000 at branch 10 is depth 6 and 1,111,111 nodes.
TREE_DEPTH = max(
    1, round(math.log(BENCHMARK_CASCADE_LARGE_SIZE, BENCHMARK_CASCADE_LARGE_BRANCH))
)


async def write_fixture_batch(models: list[AtomicRedisModel]) -> None:
    """
    Persist already-built fixture models straight through a Redis pipeline.
    """
    # Not ainsert: it is quadratic in batch size for Reference-carrying models
    # (4k nodes ~30s vs ~0.1s edge-free), so a million-node fixture never finishes.
    redis = AtomicRedisModel.Meta.redis
    async with redis.pipeline(transaction=False) as pipe:
        for model in models:
            pipe.json().set(model.key, model.json_path, model.redis_dump())
        await pipe.execute()


class LargeCascadeBenchmark(AsyncBenchmarkTest):
    """
    Times one cascade over a graph of BENCHMARK_CASCADE_LARGE_SIZE nodes.
    """

    # Building the graph dwarfs the call being timed, and the cascade does not
    # mutate it, so the fixture is built once per test and reused across rounds.
    rounds = 3
    warmup_rounds = 1
    # setup() assigns onto the instance, so the three shapes never share a fixture.
    _root: Any = None

    async def build(self, cls: type[AtomicRedisModel]) -> AtomicRedisModel:
        raise NotImplementedError()

    async def setup(self, mode: TTLMode) -> AtomicRedisModel:
        if self._root is None:
            self._root = await self.build(self.models[mode])
        return self._root

    async def action(self, root: AtomicRedisModel) -> Any:
        return await root.aset_ttl(BENCHMARK_TTL_SECONDS, cascade=True)


class TestCascadeTtlLargeFanOut(LargeCascadeBenchmark):
    """One root over edge-free leaves: the widest possible single-hop walk."""

    models = {TTLMode.NO_TTL: BenchCascadeLargeFanRoot}

    async def build(self, cls):
        keys = []
        for start in range(0, BENCHMARK_CASCADE_LARGE_SIZE, INSERT_BATCH):
            width = min(INSERT_BATCH, BENCHMARK_CASCADE_LARGE_SIZE - start)
            leaves = [
                BenchCascadeLargeLeaf(name=f"leaf-{start + i}") for i in range(width)
            ]
            await write_fixture_batch(leaves)
            keys.extend(leaf.key for leaf in leaves)
        root = cls(name="root", children=keys)
        await root.asave()
        return root


class TestCascadeTtlLargeChain(LargeCascadeBenchmark):
    """A chain one hop per node: the deepest possible walk."""

    models = {TTLMode.NO_TTL: BenchCascadeLargeChainNode}

    async def build(self, cls):
        # Tail-first so each node references an already-minted child key, and only
        # the current batch is held rather than the whole graph.
        head_key = None
        batch = []
        for index in range(BENCHMARK_CASCADE_LARGE_SIZE):
            node = cls(name=f"node-{index}", next=head_key)
            head_key = node.key
            batch.append(node)
            if len(batch) >= INSERT_BATCH:
                await write_fixture_batch(batch)
                batch.clear()
        if batch:
            await write_fixture_batch(batch)
        return await cls.aget(head_key)


class TestCascadeTtlLargeTree(LargeCascadeBenchmark):
    """A branching tree, where every interior node costs its own JSON.GET."""

    models = {TTLMode.NO_TTL: BenchCascadeLargeTreeNode}

    async def build(self, cls):
        # Leaves upward, so a parent always has real child keys to reference.
        level: list[str] = []
        for exponent in range(TREE_DEPTH, -1, -1):
            parents = []
            batch = []
            for index in range(BENCHMARK_CASCADE_LARGE_BRANCH**exponent):
                start = index * BENCHMARK_CASCADE_LARGE_BRANCH
                node = cls(
                    name=f"node-{exponent}-{index}",
                    children=level[start : start + BENCHMARK_CASCADE_LARGE_BRANCH],
                )
                parents.append(node.key)
                batch.append(node)
                if len(batch) >= INSERT_BATCH:
                    await write_fixture_batch(batch)
                    batch.clear()
            if batch:
                await write_fixture_batch(batch)
            level = parents
        return await cls.aget(level[0])
