from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel


class DeleteResult(BaseModel):
    count: int


class ModuleDeleteResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    count: int
    by_model: dict[type[AtomicRedisModel], int]
