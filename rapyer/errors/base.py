class RapyerError(Exception):
    """Base exception for all rapyer errors."""

    pass


class KeyNotFound(RapyerError):
    """Raised when a key is not found in Redis."""

    pass


class RapyerModelDoesntExistError(RapyerError):
    """Raised when a model doesn't exist."""

    def __init__(self, model_name: str, *args):
        super().__init__(*args)
        self.model_name = model_name


class MissingParameterError(RapyerError):
    """Raised when a required parameter is missing."""
