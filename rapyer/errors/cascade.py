from rapyer.errors.base import RapyerError


class InvalidCascadeDepthError(RapyerError):
    """Raised when a ``CascadeSpec``'s ``depth`` is negative."""


class CascadeTargetTtlMissingError(RapyerError):
    """Raised at init_rapyer() when a cascade-reachable model has no Meta.ttl."""

    def __init__(self, model_name: str, *args):
        super().__init__(*args)
        self.model_name = model_name


class CascadeKeyInitialsError(RapyerError):
    """Raised at init_rapyer() when a cascade participant overrides
    class_key_initials() to a value other than __name__.

    The cascade plan and ``edge.candidates`` are keyed by ``cls.__name__``, but
    the real Redis key prefix is ``class_key_initials()`` (an overridable
    classmethod defaulting to ``__name__``). Reached-key class resolution splits
    the ``{class}:{pk}`` prefix and matches it against those ``__name__``-keyed
    candidates, so an override ``!= __name__`` would silently mis-resolve or
    dead-end the cascade. Carries the offending ``model_name`` like
    CascadeTargetTtlMissingError.
    """

    def __init__(self, model_name: str, *args):
        super().__init__(*args)
        self.model_name = model_name


class MetaFrozenError(RapyerError):
    """Raised when Meta config is mutated after init_rapyer() has baked the cascade plan against it."""


class CascadeLuaLiteralError(RapyerError):
    """Raised when a cascade plan cannot be safely embedded as a Lua long-bracket literal."""
