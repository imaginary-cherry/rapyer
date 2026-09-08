from typing import Annotated, Optional

import pytest

from rapyer.types.redis_set import RedisSet
from rapyer.utils.annotation import annotation_origin


@pytest.mark.parametrize(
    ["annotation", "expected"],
    [
        [RedisSet[str], RedisSet],
        [Optional[RedisSet[str]], RedisSet],
        [Annotated[RedisSet[str], "meta"], RedisSet],
        [Annotated[Optional[RedisSet[str]], "meta"], RedisSet],
        # Optional outside Annotated must still resolve to the inner type.
        [Optional[Annotated[RedisSet[str], "meta"]], RedisSet],
        [Optional[Annotated[str, "meta"]], str],
        [Annotated[Optional[Annotated[RedisSet[str], "a"]], "b"], RedisSet],
        [Optional[Annotated[Optional[RedisSet[str]], "a"]], RedisSet],
    ],
)
def test_annotation_origin_peels_wrappers_in_either_order(annotation, expected):
    assert annotation_origin(annotation) is expected
