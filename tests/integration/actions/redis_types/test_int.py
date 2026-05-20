from rapyer.types.integer import RedisInt
from tests.integration.actions.base import BinaryOpCase
from tests.integration.actions.comprehensive import ComprehensiveCounterOpBase
from tests.integration.actions.sync_action import SyncActionTestBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestIntegerAddition(UpdateActionTestBase, SyncActionTestBase):
    covered_method = RedisInt.__iadd__
    skip_stale_mirror_in_pipeline = (
        "scalar value is its own mirror; no stale-mirror failure mode"
    )
    skip_sync_native_raises_on_corruption = (
        "int arithmetic never raises on a stale value"
    )

    def create_models(self):
        return [ComprehensiveTestModel(counter=100)]

    async def perform_action(self, piped):
        piped.counter += 25

    def apply_native_action(self, native: int) -> int:
        return native + 25

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.counter

    def expected_before(self):
        return 100

    def expected_after(self):
        return 125

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.counter += 7919

    def get_target_field(self, m: ComprehensiveTestModel) -> int:
        return int(m.counter)


class TestRedisIntAincrease(ComprehensiveCounterOpBase, TTLActionTestBase):
    covered_method = RedisInt.aincrease

    def create_models(self):
        return [ComprehensiveTestModel(counter=10)]

    async def perform_action(self, piped: ComprehensiveTestModel) -> None:
        await piped.counter.aincrease(5)

    def expected_before(self):
        return 10

    def expected_after(self):
        return 15


class TestRedisIntIsub(ComprehensiveCounterOpBase, SyncActionTestBase):
    covered_method = RedisInt.__isub__
    params = [
        BinaryOpCase(20, 5, 15),
        BinaryOpCase(100, 30, 70),
        BinaryOpCase(50, 50, 0),
    ]

    async def perform_action(self, piped):
        piped.counter -= self.test_input.operand

    def apply_native_action(self, native: int) -> int:
        return native - self.test_input.operand


class TestRedisIntImul(ComprehensiveCounterOpBase, SyncActionTestBase):
    covered_method = RedisInt.__imul__
    params = [
        BinaryOpCase(5, 4, 20),
        BinaryOpCase(10, 3, 30),
        BinaryOpCase(7, 0, 0),
    ]

    async def perform_action(self, piped):
        piped.counter *= self.test_input.operand

    def apply_native_action(self, native: int) -> int:
        return native * self.test_input.operand


class TestRedisIntIfloordiv(ComprehensiveCounterOpBase, SyncActionTestBase):
    covered_method = RedisInt.__ifloordiv__
    params = [
        BinaryOpCase(17, 5, 3),
        BinaryOpCase(100, 7, 14),
        BinaryOpCase(25, 4, 6),
    ]

    async def perform_action(self, piped):
        piped.counter //= self.test_input.operand

    def apply_native_action(self, native: int) -> int:
        return native // self.test_input.operand


class TestRedisIntImod(ComprehensiveCounterOpBase, SyncActionTestBase):
    covered_method = RedisInt.__imod__
    params = [
        BinaryOpCase(17, 5, 2),
        BinaryOpCase(23, 7, 2),
        BinaryOpCase(100, 9, 1),
    ]

    async def perform_action(self, piped):
        piped.counter %= self.test_input.operand

    def apply_native_action(self, native: int) -> int:
        return native % self.test_input.operand


class TestRedisIntIpow(ComprehensiveCounterOpBase, SyncActionTestBase):
    covered_method = RedisInt.__ipow__
    params = [
        BinaryOpCase(2, 3, 8),
        BinaryOpCase(3, 2, 9),
        BinaryOpCase(5, 2, 25),
    ]

    async def perform_action(self, piped):
        piped.counter **= self.test_input.operand

    def apply_native_action(self, native: int) -> int:
        return native**self.test_input.operand
