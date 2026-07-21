from rapyer.errors.base import RapyerError


class EmbeddingsExtraNotInstalledError(RapyerError):
    """Raised when an embeddings feature needs an optional extra that is not installed."""

    def __init__(self, extra_name: str, *args):
        super().__init__(*args)
        self.extra_name = extra_name
