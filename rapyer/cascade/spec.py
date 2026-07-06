import abc
import dataclasses
import enum

from rapyer.errors.cascade import InvalidCascadeDepthError


class TTLCascadeMode(enum.Enum):
    """How a cascaded TTL is applied relative to the child's existing TTL.

    - ``EXTEND``: only raise the child's TTL if the cascaded value is longer.
    - (future modes, e.g. ``OVERWRITE``/``IF_UNSET``, land here without
      touching ``CascadeTTL``'s shape.)
    """

    EXTEND = "extend"


@dataclasses.dataclass(frozen=True)
class CascadeSpec(abc.ABC):
    """Shared data contract for every cascade strategy (EXT-01 extension seam).

    Future strategies (``CascadeDelete``/``CascadeSave``) subclass this to
    reuse the same ``enabled``/``depth`` surface and the same traversal
    backbone; only the apply step differs per strategy.
    """

    enabled: bool = True
    depth: int | None = None

    def __post_init__(self):
        if self.depth is not None and self.depth < 0:
            raise InvalidCascadeDepthError(
                f"depth must be None or >= 0, got {self.depth!r}"
            )
