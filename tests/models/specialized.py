from pydantic import ConfigDict, Field

from rapyer.base import AtomicRedisModel


class UserModel(AtomicRedisModel):
    tags: list[str] = Field(default_factory=list)


class ModelWithConfig(AtomicRedisModel):
    tags: list[str] = Field(default_factory=list)
    int_field: int = 2
    model_config = ConfigDict(title="Test Model Config")
