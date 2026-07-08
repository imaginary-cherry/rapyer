import pytest_asyncio

from tests.models.foreign_key_types import FkAuthor, FkBook, FkPublisher

MISSING_AUTHOR_KEY = "FkAuthor:missing"
MISSING_PUBLISHER_KEY = "FkPublisher:missing"


@pytest_asyncio.fixture
async def saved_author(real_redis_client):
    author = FkAuthor(name="Toni Morrison", age=88)
    await author.asave()
    return author


@pytest_asyncio.fixture
async def saved_publisher(real_redis_client):
    publisher = FkPublisher(name="Knopf", country="US")
    await publisher.asave()
    return publisher


@pytest_asyncio.fixture
async def book_with_author(real_redis_client, saved_author):
    book = FkBook(title="Beloved", author=saved_author.key)
    await book.asave()
    return book, saved_author


@pytest_asyncio.fixture
async def book_with_missing_author(real_redis_client):
    book = FkBook(title="Ghost", author=MISSING_AUTHOR_KEY)
    await book.asave()
    return book


@pytest_asyncio.fixture
async def book_with_publisher(real_redis_client, saved_author, saved_publisher):
    book = FkBook(
        title="Beloved", author=saved_author.key, publisher=saved_publisher.key
    )
    await book.asave()
    return book, saved_publisher


@pytest_asyncio.fixture
async def book_with_missing_publisher(real_redis_client, saved_author):
    book = FkBook(
        title="Ghost", author=saved_author.key, publisher=MISSING_PUBLISHER_KEY
    )
    await book.asave()
    return book
