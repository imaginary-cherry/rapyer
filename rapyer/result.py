from pydantic import BaseModel


class DeleteResult(BaseModel):
    count: int
