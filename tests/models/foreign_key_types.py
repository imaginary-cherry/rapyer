from typing import ClassVar, Optional

from pydantic import Field

from rapyer.actions import ActionGroup
from rapyer.base import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.types.foreign_key import Reference
from rapyer.types.redis_set import RedisSet

FK_TTL_SECONDS = 24


class FkProfile(AtomicRedisModel):
    bio: str = ""


class FkAuthor(AtomicRedisModel):
    name: str = "anon"
    age: int = 0


class FkRichAuthor(AtomicRedisModel):
    name: str = "anon"
    profile: FkProfile = Field(default_factory=FkProfile)
    tags: RedisSet[str] = Field(default_factory=RedisSet)


class FkLibrary(AtomicRedisModel):
    name: str = "lib"
    head_author: Reference[FkRichAuthor]


class FkPublisher(AtomicRedisModel):
    name: str = "nameless press"
    country: str = ""


class FkBook(AtomicRedisModel):
    title: str = "untitled"
    author: Reference[FkAuthor]
    publisher: Optional[Reference[FkPublisher]] = None
    co_authors: list[Reference[FkAuthor]] = Field(default_factory=list)


class FkTree(AtomicRedisModel):
    name: str = "root"
    parent: Optional[Reference["FkTree"]] = None


class FkTTLReferee(AtomicRedisModel):
    """Referenced model that refreshes TTL on writes only, never on reads/fetches."""

    name: str = "referee"

    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=FK_TTL_SECONDS,
        refresh_ttl=ActionGroup.CREATE | ActionGroup.UPDATE | ActionGroup.APPEND,
    )


class FkTTLOwner(AtomicRedisModel):
    """Main model that refreshes TTL on read, fetch and update."""

    title: str = "owner"
    referee: Reference[FkTTLReferee]

    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=FK_TTL_SECONDS,
        refresh_ttl=ActionGroup.READ | ActionGroup.FETCH | ActionGroup.UPDATE,
    )
