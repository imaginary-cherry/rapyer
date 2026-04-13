from rapyer.types.integer import RedisInt
from tests.integration.pipeline.pipeline_atomicity_base import (
    BinaryOpCase,
    ComprehensiveCounterOpBase,
)


class TestRedisIntIsub(ComprehensiveCounterOpBase):
    covered_method = RedisInt.__isub__
    params = [
        BinaryOpCase(20, 5, 15),
        BinaryOpCase(100, 30, 70),
        BinaryOpCase(50, 50, 0),
    ]

    async def perform_action(self, piped):
        piped.counter -= self.test_input.operand


class TestRedisIntImul(ComprehensiveCounterOpBase):
    covered_method = RedisInt.__imul__
    params = [
        BinaryOpCase(5, 4, 20),
        BinaryOpCase(10, 3, 30),
        BinaryOpCase(7, 0, 0),
    ]

    async def perform_action(self, piped):
        piped.counter *= self.test_input.operand


class TestRedisIntIfloordiv(ComprehensiveCounterOpBase):
    covered_method = RedisInt.__ifloordiv__
    params = [
        BinaryOpCase(17, 5, 3),
        BinaryOpCase(100, 7, 14),
        BinaryOpCase(25, 4, 6),
    ]

    async def perform_action(self, piped):
        piped.counter //= self.test_input.operand


class TestRedisIntImod(ComprehensiveCounterOpBase):
    covered_method = RedisInt.__imod__
    params = [
        BinaryOpCase(17, 5, 2),
        BinaryOpCase(23, 7, 2),
        BinaryOpCase(100, 9, 1),
    ]

    async def perform_action(self, piped):
        piped.counter %= self.test_input.operand


class TestRedisIntIpow(ComprehensiveCounterOpBase):
    covered_method = RedisInt.__ipow__
    params = [
        BinaryOpCase(2, 3, 8),
        BinaryOpCase(3, 2, 9),
        BinaryOpCase(5, 2, 25),
    ]

    async def perform_action(self, piped):
        piped.counter **= self.test_input.operand
