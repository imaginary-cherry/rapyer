from __future__ import annotations

import warnings
from enum import Enum
from typing import TYPE_CHECKING, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel


class DeleteResult(BaseModel):
    models_deleted: int
    keys_deleted: int
    was_committed: bool = True

    @property
    def count(self) -> int:
        warnings.warn(
            "DeleteResult.count is deprecated, use .models_deleted instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.models_deleted


class RapyerDeleteResult(DeleteResult):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    by_model: dict[type[AtomicRedisModel], int]


class CascadeResult(BaseModel):
    dangling_children: int
    dangling_special: int
    # Count of MULTI-CLASS reaches whose resolved class was not among the edge's
    # candidate targets (or was absent from the plan) -- server-side class-drift
    # observability (D-03). Defaulted to 0 so existing construction sites stay
    # forward-compatible; the Lua/apply lockstep sites set it explicitly.
    mismatched_class: int = 0


class GetOrCreateStatus(str, Enum):
    CREATED = "created"
    FOUND = "found"


T = TypeVar("T", bound="AtomicRedisModel")


class GetOrCreateResult(BaseModel, Generic[T]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    value: T
    status: GetOrCreateStatus


def resolve_forward_refs():
    from rapyer.base import AtomicRedisModel

    RapyerDeleteResult.model_rebuild(
        _types_namespace={"AtomicRedisModel": AtomicRedisModel}
    )
    GetOrCreateResult.model_rebuild(
        _types_namespace={"AtomicRedisModel": AtomicRedisModel}
    )
