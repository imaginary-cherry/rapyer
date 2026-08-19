from typing import ClassVar
from unittest.mock import MagicMock

from rapyer.base import AtomicRedisModel, RedisConfig
from rapyer.types.text import RedisText


class BaselineTransplantModel(AtomicRedisModel):
    body: RedisText = ""
    label: str = ""

    Meta: ClassVar[RedisConfig] = RedisConfig(redis=MagicMock())


def test_reassigning_same_text_keeps_baseline_clean():
    model = BaselineTransplantModel(body="original")
    model.body._baseline_text = "original"

    model.body = "original"

    assert model.body._baseline_text == "original"
    assert model.body.pending_embed_text() is None


def test_reassigning_different_text_keeps_old_baseline_dirty():
    model = BaselineTransplantModel(body="original")
    model.body._baseline_text = "original"

    model.body = "changed"

    assert model.body._baseline_text == "original"
    assert model.body.pending_embed_text() == "changed"


def test_first_assignment_on_fresh_model_does_not_raise():
    model = BaselineTransplantModel(body="hi")

    assert model.body == "hi"


def test_non_redistext_field_reassignment_unaffected():
    model = BaselineTransplantModel(body="hi", label="a")

    model.label = "b"

    assert model.label == "b"
