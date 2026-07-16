import pytest_asyncio

from rapyer.cascade.planner import (
    build_cascade_plan,
    cascade_plan_json,
)
from rapyer.scripts import register_cascade_function, register_scripts
from rapyer.types.relational import resolve_relational_targets
from tests.models.cascade_types import ALL_CASCADE_MODELS
from tests.models.foreign_key_types import FkAuthor, FkBook, FkPublisher

MISSING_AUTHOR_KEY = "FkAuthor:missing"
MISSING_PUBLISHER_KEY = "FkPublisher:missing"

# Full cascade set so the baked plan covers every reachable edge target.
CASCADE_INTEGRATION_MODELS = ALL_CASCADE_MODELS


@pytest_asyncio.fixture
async def setup_real_redis_for_cascade_apply(
    real_redis_client, requires_redis_functions
):
    original_clients = {}
    for model in CASCADE_INTEGRATION_MODELS:
        original_clients[model] = (model.Meta.redis, model.Meta.is_fake_redis)
        model.Meta.redis = real_redis_client
        model.Meta.is_fake_redis = False
    resolve_relational_targets(CASCADE_INTEGRATION_MODELS)
    await register_scripts(real_redis_client, is_fakeredis=False)
    # Emulate init_rapyer: bake the plan into the cascade function and load it.
    await register_cascade_function(
        real_redis_client,
        cascade_plan_json(build_cascade_plan(CASCADE_INTEGRATION_MODELS)),
    )
    yield
    for model, (original_redis, original_is_fake) in original_clients.items():
        model.Meta.redis = original_redis
        model.Meta.is_fake_redis = original_is_fake


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
