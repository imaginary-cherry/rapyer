import dataclasses


@dataclasses.dataclass(frozen=True)
class VectorAnnotation:
    dim: int
    metric: str = "COSINE"
    algorithm: str = "FLAT"


def Vector(
    *, dim: int, metric: str = "COSINE", algorithm: str = "FLAT"
) -> VectorAnnotation:
    return VectorAnnotation(dim=dim, metric=metric, algorithm=algorithm)
