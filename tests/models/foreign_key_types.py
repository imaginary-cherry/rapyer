from typing import Optional

from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.types.foreign_key import Reference
from rapyer.types.redis_set import RedisSet


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
