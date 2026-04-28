from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel  # pragma: no cover


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


def resolve_forward_refs():
    from rapyer.base import AtomicRedisModel

    RapyerDeleteResult.model_rebuild(
        _types_namespace={"AtomicRedisModel": AtomicRedisModel}
    )
