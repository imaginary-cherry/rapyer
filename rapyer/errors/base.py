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


class FindError(RapyerError):
    """Raised when a model cannot be found."""

    pass


class BadFilterError(FindError):
    """Raised when a filter is invalid."""

    pass


class UnsupportedIndexedFieldError(FindError):
    pass


class CantSerializeRedisValueError(RapyerError):
    pass


class ScriptsNotInitializedError(RapyerError):
    pass


class PersistentNoScriptError(RapyerError):
    pass
