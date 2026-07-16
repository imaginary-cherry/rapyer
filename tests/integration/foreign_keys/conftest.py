import pytest_asyncio

from rapyer.cascade.planner import (
    build_cascade_plan,
    cascade_plan_json,
)
from rapyer.scripts import register_scripts
from rapyer.types.relational import resolve_relational_targets
from rapyer.types.special import CASCADE_PLAN_KEY
from tests.models.cascade_types import (
    CascadeAuthor,
    CascadeBookCollection,
    CascadeChainNode,
    CascadeChainRoot,
    CascadeDiamondChild,
    CascadeDiamondRoot,
    CascadeDictCollectionRoot,
    CascadeSpecialChild,
    CascadeSpecialParent,
)
from tests.models.foreign_key_types import FkAuthor, FkBook, FkPublisher

MISSING_AUTHOR_KEY = "FkAuthor:missing"
MISSING_PUBLISHER_KEY = "FkPublisher:missing"

# Not in tests/models/registry.py::TESTED_REDIS_MODELS, so the autouse
# real_redis_client fixture (tests/integration/conftest.py) does not wire
# their Meta.redis automatically — this plan's cascade fixtures need it
# wired explicitly, mirroring setup_fake_redis_for_cascade_apply's
# save/restore shape but against the real client.
#
# 04-05: widened with a purpose-built subset (not the full 25-class
# fakeredis CASCADE_PLANNER_MODELS list) covering ROADMAP criterion 1's
# named graph shapes -- CascadeChainNode/CascadeChainRoot for
# multi-level/cyclic/self-reference, CascadeDiamondChild/CascadeDiamondRoot
# for diamond dedup.
CASCADE_INTEGRATION_MODELS = [
    CascadeAuthor,
    CascadeBookCollection,
    CascadeDictCollectionRoot,
    CascadeSpecialChild,
    CascadeSpecialParent,
    CascadeChainNode,
    CascadeChainRoot,
    CascadeDiamondChild,
    CascadeDiamondRoot,
]


@pytest_asyncio.fixture
async def setup_real_redis_for_cascade_apply(real_redis_client):
    original_clients = {}
    for model in CASCADE_INTEGRATION_MODELS:
        original_clients[model] = (model.Meta.redis, model.Meta.is_fake_redis)
        model.Meta.redis = real_redis_client
        model.Meta.is_fake_redis = False
    resolve_relational_targets(CASCADE_INTEGRATION_MODELS)
    await register_scripts(real_redis_client, is_fakeredis=False)
    # The full plan lives in one Redis key read server-side; emulate init_rapyer
    # by writing it after register_scripts.
    await real_redis_client.set(
        CASCADE_PLAN_KEY,
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
