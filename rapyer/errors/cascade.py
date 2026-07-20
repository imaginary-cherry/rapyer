from rapyer.errors.base import RapyerError


class InvalidCascadeDepthError(RapyerError):
    """Raised when a ``CascadeSpec``'s ``depth`` is negative."""


class CascadeTargetTtlMissingError(RapyerError):
    """Raised at init_rapyer() when a cascade-reachable model has no Meta.ttl."""

    def __init__(self, model_name: str, *args):
        super().__init__(*args)
        self.model_name = model_name


class MetaFrozenError(RapyerError):
    """Raised when Meta config is mutated after init_rapyer() has baked the cascade plan against it."""


class CascadeLuaLiteralError(RapyerError):
    """Raised when a cascade plan cannot be safely embedded as a Lua long-bracket literal."""
