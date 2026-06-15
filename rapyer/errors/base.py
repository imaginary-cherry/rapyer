class RapyerError(Exception):
    """Base exception for all rapyer errors."""

    pass


class KeyNotFound(RapyerError):
    """Raised when a key is not found in Redis."""

    pass


class CorruptedModelError(RapyerError):
    """Raised when a model is corrupted."""

    pass


class RapyerModelDoesntExistError(RapyerError):
    """Raised when a model doesn't exist."""

    def __init__(self, model_name: str, *args):
        super().__init__(*args)
        self.model_name = model_name


class MissingParameterError(RapyerError):
    """Raised when a required parameter is missing."""


class UnsupportedArgumentValueError(RapyerError):
    pass


class UpdateAtomicModelError(RapyerError):
    pass


class InvalidRefreshTtlError(RapyerError):
    """Raised when refresh_ttl contains ActionGroup.DELETE, which is never refreshable."""


class DuplicateModelNameError(RapyerError):
    """Raised when two registered models share the same class name."""

    def __init__(self, model_name: str, *args):
        super().__init__(*args)
        self.model_name = model_name


class RapyerSerializationError(RapyerError):
    pass


class NotResolvedError(RapyerError):
    """Raised when accessing the hydrated value of an unresolved relational field."""
