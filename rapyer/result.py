from pydantic import BaseModel


class DeleteResult(BaseModel):
    count: int


class ModuleDeleteResult(BaseModel):
    count: int
    by_model: dict[str, int]
