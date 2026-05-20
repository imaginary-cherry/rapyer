from datetime import datetime

from rapyer.types.byte import RedisBytes
from rapyer.types.datetime import RedisDatetime
from rapyer.types.dct import RedisDict
from rapyer.types.float import RedisFloat
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.redis_set import RedisSet
from rapyer.types.string import RedisStr

ALL_TYPES = {
    list: RedisList,
    dict: RedisDict,
    set: RedisSet,
    bytes: RedisBytes,
    int: RedisInt,
    float: RedisFloat,
    str: RedisStr,
    datetime: RedisDatetime,
}
