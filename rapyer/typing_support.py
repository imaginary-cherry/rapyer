# For python 3.10 support
try:
    from typing import Self, Unpack
except ImportError:  # pragma: no cover
    from typing_extensions import Self, Unpack  # pragma: no cover

__all__ = ["Self", "Unpack"]
