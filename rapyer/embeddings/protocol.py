from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingAdapter(Protocol):
    @property
    def dims(self) -> int: ...  # pragma: no cover

    async def aembed(self, content: str) -> list[float]: ...  # pragma: no cover

    async def aembed_many(
        self, contents: list[str]
    ) -> list[list[float]]: ...  # pragma: no cover
