from typing import ClassVar, Optional

from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.types.foreign_key import Reference
from rapyer.types.redis_set import RedisSet

FK_AFETCH_TTL_SECONDS = 24


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


class FkAfetchTarget(AtomicRedisModel):
    # The model afetch resolves and refreshes (target=RESULT). It carries TTL so
    # the refresh is observable; the afetch action test checks this key.
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=FK_AFETCH_TTL_SECONDS)
    name: str = "anon"
    age: int = 0


class FkAfetchOwner(AtomicRedisModel):
    # The owner gates afetch's refresh under V2 (the wrap decision uses this
    # model's TTL-refresh config at install time), so it carries TTL and is the
    # model the afetch action test toggles.
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=FK_AFETCH_TTL_SECONDS)
    ref: Reference[FkAfetchTarget]
