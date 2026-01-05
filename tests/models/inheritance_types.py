from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field, BaseModel

from rapyer.base import AtomicRedisModel


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class BaseUserModel(AtomicRedisModel):
    name: str = "default_user"
    email: str = Field(default="user@example.com")
    age: int = Field(default=25, ge=0, le=150)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    role: UserRole = UserRole.USER
    optional_field: str | None = None
    scores: list[int] = Field(default_factory=lambda: [100, 200])


class AdminUserModel(BaseUserModel):
    admin_level: int = Field(default=1, ge=1, le=10)
    permissions: list[str] = Field(default_factory=lambda: ["read", "write"])
    managed_users: dict[str, str] = Field(default_factory=dict)
    last_login: datetime = Field(default_factory=datetime.now)
    is_super_admin: bool = False
    admin_notes: str = "No notes"
    backup_email: str | None = None
    access_codes: list[int] = Field(default_factory=lambda: [1001, 1002])


class SimpleBaseModel(BaseModel):
    username: str = "test_user"
    score: int = 100
    active: bool = True


class HybridModel(AtomicRedisModel, SimpleBaseModel):
    redis_field: str = "redis_value"
    count: int = 42


class NonPydanticClass:
    def __init__(self):
        self.non_pydantic_field = "should_not_persist"
        self.another_field = 999
        self.temp_data = {"key": "value"}


class StrictMixedInheritanceModel(AtomicRedisModel):
    redis_data: str = "test_data"
    number: int = 123

    model_config = {"extra": "ignore"}

    def __init__(self, **data):
        AtomicRedisModel.__init__(self, **data)
        # Set non-pydantic fields after initialization
        self.__dict__["non_pydantic_field"] = "should_not_persist"
        self.__dict__["another_field"] = 999
        self.__dict__["temp_data"] = {"key": "value"}
