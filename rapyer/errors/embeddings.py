from rapyer.errors.base import RapyerError


class EmbeddingsExtraNotInstalledError(RapyerError):
    """Raised when an embeddings feature needs an optional extra that is not installed."""

    def __init__(self, extra_name: str, *args):
        super().__init__(*args)
        self.extra_name = extra_name


class VectorDimMismatchError(RapyerError):
    """Raised when a computed embedding's dim doesn't match the field's declared dim."""

    def __init__(self, field_name: str, declared_dim: int, actual_dim: int, *args):
        super().__init__(*args)
        self.field_name = field_name
        self.declared_dim = declared_dim
        self.actual_dim = actual_dim


class RedisTextEmbeddingNotMaterializedError(RapyerError):
    """Raised when a RedisText field is saved before its embedding was materialized."""

    def __init__(self, field_path: str, *args):
        super().__init__(*args)
        self.field_path = field_path


class RedisTextRealRedisRequiredError(RapyerError):
    """Raised when a RedisText-bearing model operation is attempted against fakeredis."""

    def __init__(self, model_name: str, *args):
        super().__init__(*args)
        self.model_name = model_name
