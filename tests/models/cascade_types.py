from typing import Annotated

from pydantic import Field

from rapyer.base import AtomicRedisModel
from rapyer.cascade import CascadeTTL
from rapyer.types.foreign_key import Reference


class CascadeAuthor(AtomicRedisModel):
    name: str = "anon"


class CascadeBookDirect(AtomicRedisModel):
    """Shape 1: direct FK field carrying an explicit CascadeTTL."""

    title: str = "untitled"
    author: Annotated[Reference[CascadeAuthor], CascadeTTL(enabled=False)]


class CascadeBookCollection(AtomicRedisModel):
    """Shape 2: collection-of-FK field carrying the marker on the collection itself."""

    title: str = "untitled"
    co_authors: Annotated[list[Reference[CascadeAuthor]], CascadeTTL()] = Field(
        default_factory=list
    )


class CascadeProfile(AtomicRedisModel):
    """Nested submodel whose own field carries the cascade marker (shape 3)."""

    mentor: Annotated[Reference[CascadeAuthor], CascadeTTL()]


class CascadeBookNested(AtomicRedisModel):
    """Shape 3: nested submodel containing its own cascade-enabled FK field."""

    title: str = "untitled"
    profile: CascadeProfile


class CascadeBookPlain(AtomicRedisModel):
    """No CascadeTTL anywhere — used for the COMPAT-02 'no marker present' case."""

    title: str = "untitled"
    author: Reference[CascadeAuthor]
