import dataclasses

from rapyer.cascade.spec import CascadeSpec, TTLCascadeMode


@dataclasses.dataclass(frozen=True)
class CascadeTTL(CascadeSpec):
    """TTL-cascade config, used directly as field metadata:

    ``Annotated[Reference[Author], CascadeTTL(enabled=False)]``.
    """

    mode: TTLCascadeMode = TTLCascadeMode.EXTEND
