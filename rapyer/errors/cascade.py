from rapyer.errors.base import RapyerError


class InvalidCascadeDepthError(RapyerError):
    """Raised when a ``CascadeSpec``'s ``depth`` is negative."""
