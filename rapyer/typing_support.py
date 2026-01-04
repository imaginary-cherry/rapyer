# For python 3.10 support
try:
    from typing import Self, Unpack
except ImportError:  # pragma: no cover
    from typing_extensions import Self, Unpack  # pragma: no cover

# For python 3.13 support
try:
    from typing import deprecated
except ImportError:
    from typing_extensions import deprecated

__all__ = ["Self", "Unpack", "deprecated"]
