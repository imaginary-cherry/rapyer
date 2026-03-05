import warnings

from rapyer.errors.base import (
    RapyerError,
    RapyerModelDoesntExistError,
    KeyNotFound,
    MissingParameterError,
    UnsupportedArgumentValueError,
)
from rapyer.errors.find import (
    BadFilterError,
    FindError,
    PersistentNoScriptError,
    ScriptsNotInitializedError,
    UnsupportedIndexedFieldError,
    CantSerializeRedisValueError,
    UnsupportedArgumentTypeError,
)


def __getattr__(name):
    if name == "UnsupportArgumentTypeError":
        warnings.warn(
            "UnsupportArgumentTypeError is deprecated, use UnsupportedArgumentTypeError instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return UnsupportedArgumentTypeError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BadFilterError",
    "FindError",
    "PersistentNoScriptError",
    "RapyerError",
    "KeyNotFound",
    "ScriptsNotInitializedError",
    "UnsupportedIndexedFieldError",
    "RapyerModelDoesntExistError",
    "CantSerializeRedisValueError",
    "MissingParameterError",
    "UnsupportedArgumentValueError",
    "UnsupportedArgumentTypeError",
]
