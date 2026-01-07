class RapyerError(Exception):
    """Base exception for all rapyer errors."""

    pass


class KeyNotFound(RapyerError):
    """Raised when a key is not found in Redis."""

    pass


class FindError(RapyerError):
    """Raised when a model cannot be found."""

    pass


class BadFilterError(FindError):
    """Raised when a filter is invalid."""

    pass


class UnsupportedIndexedFieldError(FindError):
    pass
