import warnings

from rapyer.errors.base import (
    KeyNotFound,
    MissingParameterError,
    RapyerError,
    RapyerModelDoesntExistError,
    UnsupportedArgumentValueError,
)
from rapyer.errors.find import (
    BadFilterError,
    CantSerializeRedisValueError,
    FindError,
    PersistentNoScriptError,
    ScriptsNotInitializedError,
    UnsupportedArgumentTypeError,
    UnsupportedIndexedFieldError,
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
