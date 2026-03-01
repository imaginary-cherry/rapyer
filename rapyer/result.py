from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel  # pragma: no cover


class DeleteResult(BaseModel):
    count: int
    was_committed: bool = True


class RapyerDeleteResult(DeleteResult):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    by_model: dict[type[AtomicRedisModel], int]


def resolve_forward_refs():
    from rapyer.base import AtomicRedisModel

    RapyerDeleteResult.model_rebuild(
        _types_namespace={"AtomicRedisModel": AtomicRedisModel}
    )
