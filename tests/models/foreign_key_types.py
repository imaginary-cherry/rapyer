from typing import Optional

from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.types.foreign_key import ForeignKey
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
    head_author: ForeignKey[FkRichAuthor]


class FkPublisher(AtomicRedisModel):
    name: str = "nameless press"
    country: str = ""


class FkBook(AtomicRedisModel):
    title: str = "untitled"
    author: ForeignKey[FkAuthor]
    publisher: Optional[ForeignKey[FkPublisher]] = None
    co_authors: list[ForeignKey[FkAuthor]] = []


class FkTree(AtomicRedisModel):
    name: str = "root"
    parent: Optional[ForeignKey["FkTree"]] = None
