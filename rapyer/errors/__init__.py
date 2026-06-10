import warnings

from rapyer.errors.base import (
    CorruptedModelError,
    DuplicateModelNameError,
    InvalidRefreshTtlError,
    KeyNotFound,
    MissingParameterError,
    NotResolvedError,
    RapyerError,
    RapyerModelDoesntExistError,
    RapyerSerializationError,
    UnsupportedArgumentValueError,
    UpdateAtomicModelError,
)
from rapyer.errors.delete import BadDeleteActionError
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
    "DuplicateModelNameError",
    "InvalidRefreshTtlError",
    "UpdateAtomicModelError",
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
    "BadDeleteActionError",
    "CorruptedModelError",
    "RapyerSerializationError",
    "NotResolvedError",
]
