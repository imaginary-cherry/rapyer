from rapyer.errors.base import RapyerError


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


class UnsupportArgumentTypeError(RapyerError):
    pass
