from typing import Annotated, ClassVar

from rapyer.base import AtomicRedisModel, RedisConfig
from rapyer.fields.vector import Vector, VectorAnnotation
from rapyer.types.text import RedisText


class _DimAdapter:
    """EmbeddingAdapter double whose dims is fixed at construction time."""

    def __init__(self, dims: int):
        self._dims = dims

    @property
    def dims(self):
        return self._dims

    async def aembed(self, content):
        return [0.0] * self._dims

    async def aembed_many(self, contents):
        return [[0.0] * self._dims for _ in contents]


# Preset dims matches the declared Vector(dim=...) to avoid tripping init.py's dim check.
class VectorFieldModel(AtomicRedisModel):
    body: Annotated[RedisText, Vector(dim=3)] = ""

    Meta: ClassVar[RedisConfig] = RedisConfig(vectorizer=_DimAdapter(3))


class BareTextFieldModel(AtomicRedisModel):
    body: RedisText = ""

    Meta: ClassVar[RedisConfig] = RedisConfig()


class OverriddenVectorDimModel(VectorFieldModel):
    body: Annotated[RedisText, Vector(dim=5)] = ""

    Meta: ClassVar[RedisConfig] = RedisConfig(vectorizer=_DimAdapter(5))


class OverriddenToPlainFieldModel(VectorFieldModel):
    body: str = ""


def test_vector_field_tracked_with_annotation():
    assert VectorFieldModel._vector_fields["body"] == VectorAnnotation(dim=3)


def test_bare_text_field_has_no_vector_annotation():
    assert "body" not in BareTextFieldModel._vector_fields


def test_subclass_override_last_declared_dim_wins():
    assert OverriddenVectorDimModel._vector_fields["body"].dim == 5
    # Parent's field-tracking dict is untouched by the subclass's own copy.
    assert VectorFieldModel._vector_fields["body"].dim == 3


def test_subclass_override_to_plain_field_drops_stale_vector_entry():
    assert "body" not in OverriddenToPlainFieldModel._vector_fields
