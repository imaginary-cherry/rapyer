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
    # TTL on, refresh off — so the inner ``aget`` that ``afetch`` delegates to
    # won't refresh this key on its own. That isolates ``ForeignKey.afetch``'s
    # own action wrapper as the sole refresher, which is what the afetch action
    # test asserts.
    Meta: ClassVar[RedisConfig] = RedisConfig(
        ttl=FK_AFETCH_TTL_SECONDS, refresh_ttl=False
    )
    name: str = "anon"
    age: int = 0


class FkAfetchOwner(AtomicRedisModel):
    # TTL on so the per-field ForeignKey gets its afetch action installed.
    Meta: ClassVar[RedisConfig] = RedisConfig(ttl=FK_AFETCH_TTL_SECONDS)
    ref: Reference[FkAfetchTarget]
