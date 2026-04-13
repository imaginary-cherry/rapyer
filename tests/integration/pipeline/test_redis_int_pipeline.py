from rapyer.types.integer import RedisInt
from tests.integration.pipeline.pipeline_atomicity_base import (
    ComprehensiveCounterOpBase,
)


class TestRedisIntIsub(ComprehensiveCounterOpBase):
    covered_method = RedisInt.__isub__
    params = [[20, 5, 15], [100, 30, 70], [50, 50, 0]]

    async def perform_action(self, piped, *, operand, **_):
        piped.counter -= operand


class TestRedisIntImul(ComprehensiveCounterOpBase):
    covered_method = RedisInt.__imul__
    params = [[5, 4, 20], [10, 3, 30], [7, 0, 0]]

    async def perform_action(self, piped, *, operand, **_):
        piped.counter *= operand


class TestRedisIntIfloordiv(ComprehensiveCounterOpBase):
    covered_method = RedisInt.__ifloordiv__
    params = [[17, 5, 3], [100, 7, 14], [25, 4, 6]]

    async def perform_action(self, piped, *, operand, **_):
        piped.counter //= operand


class TestRedisIntImod(ComprehensiveCounterOpBase):
    covered_method = RedisInt.__imod__
    params = [[17, 5, 2], [23, 7, 2], [100, 9, 1]]

    async def perform_action(self, piped, *, operand, **_):
        piped.counter %= operand


class TestRedisIntIpow(ComprehensiveCounterOpBase):
    covered_method = RedisInt.__ipow__
    params = [[2, 3, 8], [3, 2, 9], [5, 2, 25]]

    async def perform_action(self, piped, *, operand, **_):
        piped.counter **= operand
