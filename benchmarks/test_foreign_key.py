from benchmarks.base import AsyncBenchmarkTest, TTLMode
from tests.models.foreign_key_types import FkAuthor, FkBook

LIST_FK_COUNT = 5


class TestForeignKeyAfetchSingle(AsyncBenchmarkTest):
    models = {TTLMode.NO_TTL: FkBook}

    async def setup(self, mode):
        cls = self.models[mode]
        author = FkAuthor(name="author")
        await author.asave()
        book = cls(title="book", author=author.key)
        await book.asave()
        return await cls.aget(book.key)

    async def action(self, book):
        return await book.author.afetch()


class TestForeignKeySaveWithSavedFk(AsyncBenchmarkTest):
    """Save a parent whose foreign-key target is already persisted."""

    models = {TTLMode.NO_TTL: FkBook}

    async def setup(self, mode):
        cls = self.models[mode]
        author = FkAuthor(name="author")
        await author.asave()
        return cls(title="book", author=author)

    async def action(self, book):
        return await book.asave()


class TestForeignKeySaveWithUnsavedFk(AsyncBenchmarkTest):
    """
    Save a parent whose foreign-key target has not been persisted yet.

    Identical to the saved-target case today (save serializes the FK to its key
    only); once save cascades to the target this path will also persist it.
    """

    models = {TTLMode.NO_TTL: FkBook}

    async def setup(self, mode):
        cls = self.models[mode]
        author = FkAuthor(name="author")
        return cls(title="book", author=author)

    async def action(self, book):
        return await book.asave()


class TestForeignKeyConstructFromKey(AsyncBenchmarkTest):
    models = {TTLMode.NO_TTL: FkBook}

    async def setup(self, mode):
        self._cls = self.models[mode]
        return "FkAuthor:abc-123"

    async def action(self, key):
        return self._cls(title="book", author=key)


class TestForeignKeySerializeFkModel(AsyncBenchmarkTest):
    models = {TTLMode.NO_TTL: FkBook}

    async def setup(self, mode):
        cls = self.models[mode]
        return cls(title="book", author=FkAuthor(name="author"))

    async def action(self, book):
        return book.redis_dump()
