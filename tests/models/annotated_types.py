from typing import Annotated

from pydantic import Field, field_validator, model_validator, BaseModel

from rapyer.base import AtomicRedisModel


class AnnotatedFieldsModel(AtomicRedisModel):
    email: Annotated[str, Field(description="Valid email address")]
    age: Annotated[int, Field(ge=0, le=150, description="Age between 0 and 150")]
    tags: Annotated[
        list[str], Field(min_length=1, max_length=10, description="List of tags")
    ]
    metadata: Annotated[dict[str, str], Field(description="Metadata dictionary")]


class SimpleAnnotatedModel(AtomicRedisModel):
    name: Annotated[str, Field(min_length=1, description="Name field")]
    count: Annotated[int, Field(ge=0, description="Count field")]
    items: Annotated[list[str], Field(default_factory=list, description="Items list")]


class ValidationFieldsModel(AtomicRedisModel):
    username: str = Field(default="default_user", min_length=3, max_length=20)
    password: str = Field(
        default="DefaultPass1",
        min_length=8,
        description="Password with minimum 8 characters",
    )
    full_name: str = Field(default="Default User", description="Full name of the user")
    roles: list[str] = Field(default_factory=list, max_length=5)
    settings: dict[str, int] = Field(default_factory=dict)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v):
        valid_roles = {"admin", "user", "moderator", "guest"}
        for role in v:
            if role not in valid_roles:
                raise ValueError(f"Invalid role: {role}")
        return v


class NestedAnnotatedModel(BaseModel):
    priority: Annotated[
        int, Field(default=1, ge=1, le=5, description="Priority level 1-5")
    ]
    status: Annotated[str, Field(default="active", description="Status")]
    flags: Annotated[
        list[bool],
        Field(default_factory=list, max_length=3, description="Feature flags"),
    ]


class ComplexAnnotatedModel(AtomicRedisModel):
    user_info: ValidationFieldsModel = Field(default_factory=ValidationFieldsModel)
    nested_data: NestedAnnotatedModel = Field(default_factory=NestedAnnotatedModel)
    identifiers: Annotated[list[int], Field(min_length=1, description="Unique IDs")]
    config: Annotated[dict[str, float], Field(description="Configuration values")]

    @model_validator(mode="after")
    def validate_model(self):
        if len(self.identifiers) > 0 and max(self.identifiers) > 10000:
            raise ValueError("Identifier values must be <= 10000")
        return self


class DefaultAnnotatedModel(AtomicRedisModel):
    title: Annotated[str, Field(description="Document title")] = "Default Title"
    count: Annotated[int, Field(ge=0, description="Count value")] = 0
    active: Annotated[bool, Field(description="Active status")] = True
    items: Annotated[list[str], Field(max_length=5)] = Field(default_factory=list)
    attributes: Annotated[dict[str, int], Field(description="Attributes")] = Field(
        default_factory=dict
    )
