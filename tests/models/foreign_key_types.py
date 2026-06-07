from typing import Optional

from rapyer.base import AtomicRedisModel
from rapyer.types.foreign_key import ForeignKey


class FkAuthor(AtomicRedisModel):
    name: str = "anon"
    age: int = 0


class FkPublisher(AtomicRedisModel):
    name: str = "nameless press"


class FkBook(AtomicRedisModel):
    title: str = "untitled"
    author: ForeignKey[FkAuthor]
    publisher: Optional[ForeignKey[FkPublisher]] = None
    co_authors: list[ForeignKey[FkAuthor]] = []


class FkTree(AtomicRedisModel):
    name: str = "root"
    parent: Optional[ForeignKey["FkTree"]] = None
