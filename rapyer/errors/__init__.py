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
from rapyer.errors.cascade import (
    CascadeLuaLiteralError,
    CascadeTargetTtlMissingError,
    InvalidCascadeDepthError,
    MetaFrozenError,
)
from rapyer.errors.delete import BadDeleteActionError
from rapyer.errors.embeddings import EmbeddingsExtraNotInstalledError
from rapyer.errors.find import (
    BadFilterError,
    CantSerializeRedisValueError,
    FindError,
    PersistentNoScriptError,
    ScriptsNotInitializedError,
    UnsupportedArgumentTypeError,
    UnsupportedIndexedFieldError,
)


# TODO - we should remove this in the 1.4.0 - this backward compatiability code
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
    "BadDeleteActionError",
    "BadFilterError",
    "CantSerializeRedisValueError",
    "CascadeLuaLiteralError",
    "CascadeTargetTtlMissingError",
    "CorruptedModelError",
    "DuplicateModelNameError",
    "EmbeddingsExtraNotInstalledError",
    "FindError",
    "InvalidCascadeDepthError",
    "InvalidRefreshTtlError",
    "KeyNotFound",
    "MetaFrozenError",
    "MissingParameterError",
    "NotResolvedError",
    "PersistentNoScriptError",
    "RapyerError",
    "RapyerModelDoesntExistError",
    "RapyerSerializationError",
    "ScriptsNotInitializedError",
    "UnsupportedArgumentTypeError",
    "UnsupportedArgumentValueError",
    "UnsupportedIndexedFieldError",
    "UpdateAtomicModelError",
]
