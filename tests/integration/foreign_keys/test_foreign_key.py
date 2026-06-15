import pytest
import pytest_asyncio

from rapyer.errors import KeyNotFound
from tests.integration.conftest import REDUCED_TTL_SECONDS
from tests.integration.foreign_keys.conftest import MISSING_AUTHOR_KEY
from tests.models.foreign_key_types import (
    FK_TTL_SECONDS,
    FkAuthor,
    FkBook,
    FkLibrary,
    FkRichAuthor,
    FkTree,
    FkTTLOwner,
    FkTTLReferee,
)

# --- Required FK (FkBook.author) ---


@pytest.mark.asyncio
async def test_loading_parent_tolerates_dangling_required_fk(book_with_missing_author):
    # Arrange / Act
    # The target was never created; loading the parent must still succeed.
    loaded = await FkBook.aget(book_with_missing_author.key)

    # Assert
    assert loaded.author.is_resolved is False
    assert loaded.author.target_key == MISSING_AUTHOR_KEY


@pytest.mark.asyncio
async def test_afetch_missing_required_target_raises(book_with_missing_author):
    # Arrange
    loaded = await FkBook.aget(book_with_missing_author.key)

    # Act / Assert
    with pytest.raises(KeyNotFound):
        await loaded.author.afetch()


@pytest.mark.asyncio
async def test_afetch_existing_required_target_extracts_all_values(book_with_author):
    # Arrange
    book, author = book_with_author
    loaded = await FkBook.aget(book.key)
    assert loaded.author.is_resolved is False

    # Act
    await loaded.author.afetch()

    # Assert
    assert loaded.author.is_resolved is True
    assert loaded.author.value.name == author.name
    assert loaded.author.value.age == author.age
    # Delegated access resolves to the same target fields.
    assert loaded.author.name == author.name
    assert loaded.author.age == author.age


# --- Optional FK (FkBook.publisher) ---


@pytest.mark.asyncio
async def test_optional_fk_none_round_trips(book_with_author):
    # Arrange
    book, _ = book_with_author

    # Act
    loaded = await FkBook.aget(book.key)

    # Assert
    assert loaded.publisher is None


@pytest.mark.asyncio
async def test_loading_parent_tolerates_dangling_optional_fk(
    book_with_missing_publisher,
):
    # Arrange / Act
    loaded = await FkBook.aget(book_with_missing_publisher.key)

    # Assert
    assert loaded.publisher is not None
    assert loaded.publisher.is_resolved is False


@pytest.mark.asyncio
async def test_afetch_missing_optional_target_raises(book_with_missing_publisher):
    # Arrange
    loaded = await FkBook.aget(book_with_missing_publisher.key)

    # Act / Assert
    with pytest.raises(KeyNotFound):
        await loaded.publisher.afetch()


@pytest.mark.asyncio
async def test_afetch_existing_optional_target_extracts_all_values(book_with_publisher):
    # Arrange
    book, publisher = book_with_publisher
    loaded = await FkBook.aget(book.key)
    assert loaded.publisher.is_resolved is False

    # Act
    await loaded.publisher.afetch()

    # Assert
    assert loaded.publisher.is_resolved is True
    assert loaded.publisher.value.name == publisher.name
    assert loaded.publisher.value.country == publisher.country


# --- Resolution mechanics ---


@pytest.mark.asyncio
async def test_resolution_state_is_in_memory_only(saved_author):
    # Arrange
    # Build the book from a resolved instance, then persist + reload.
    book = FkBook(title="x", author=saved_author)
    assert book.author.is_resolved is True
    await book.asave()

    # Act
    loaded = await FkBook.aget(book.key)

    # Assert
    # Resolution does not survive a save/load cycle — only the key is stored.
    assert loaded.author.is_resolved is False
    assert loaded.author.target_key == saved_author.key


@pytest.mark.asyncio
async def test_afetch_is_idempotent(book_with_author):
    # Arrange
    book, _ = book_with_author
    loaded = await FkBook.aget(book.key)

    # Act
    first = await loaded.author.afetch()
    second = await loaded.author.afetch()

    # Assert
    # Second call returns the cached value (no re-fetch from Redis).
    assert first is second


@pytest.mark.asyncio
async def test_aunload_clears_value_preserves_key(book_with_author):
    # Arrange
    book, author = book_with_author
    loaded = await FkBook.aget(book.key)
    await loaded.author.afetch()
    assert loaded.author.is_resolved is True

    # Act
    await loaded.author.aunload()

    # Assert
    assert loaded.author.is_resolved is False
    assert loaded.author.target_key == author.key


@pytest.mark.asyncio
async def test_resolved_fk_reserializes_to_target_key(book_with_author):
    # Arrange
    book, author = book_with_author
    loaded = await FkBook.aget(book.key)
    await loaded.author.afetch()

    # Act
    # Re-save the parent while the FK is resolved, then reload.
    await loaded.asave()
    reloaded = await FkBook.aget(book.key)

    # Assert
    # The wrapper serializes back to the key string, not the hydrated model.
    assert reloaded.author.is_resolved is False
    assert reloaded.author.target_key == author.key


# --- Resolved target is a detached top-level model ---


@pytest.mark.asyncio
async def test_resolved_target_uses_its_own_paths_not_parent_path():
    # Arrange
    # The target carries its own nested + special fields; if it were treated as
    # embedded in the parent, those would be prefixed with the FK's path
    # (".head_author") and read the wrong Redis keys.
    author = FkRichAuthor(name="alice")
    await author.asave()
    await author.tags.aadd("python")
    library = FkLibrary(name="central", head_author=author.key)
    await library.asave()
    loaded = await FkLibrary.aget(library.key)

    # Act
    await loaded.head_author.afetch()
    target = loaded.head_author.value

    # Assert
    assert target.key == author.key
    # Inner field paths belong to the target, not chained through ".head_author".
    assert target.profile.field_path == ".profile"
    assert target.tags.special_key.endswith(":tags")
    # The special field reads its own key, so the member round-trips.
    assert await target.tags.amembers() == {"python"}


# --- List of FKs ---


@pytest.mark.asyncio
async def test_list_of_foreign_keys_resolve_independently():
    # Arrange
    a1 = FkAuthor(name="a1")
    a2 = FkAuthor(name="a2")
    await a1.asave()
    await a2.asave()
    book = FkBook(title="x", author=a1, co_authors=[a1, a2])
    await book.asave()
    loaded = await FkBook.aget(book.key)
    assert loaded.co_authors[0].target_key == a1.key
    assert loaded.co_authors[1].target_key == a2.key

    # Act
    await loaded.co_authors[0].afetch()

    # Assert
    # Resolving one element does not resolve the others.
    assert loaded.co_authors[0].value.name == "a1"
    assert loaded.co_authors[1].is_resolved is False


# --- Forward reference (self-link) ---


@pytest.mark.asyncio
async def test_forward_ref_self_link():
    # Arrange
    root = FkTree(name="root")
    await root.asave()
    child = FkTree(name="child", parent=root)
    await child.asave()
    loaded = await FkTree.aget(child.key)
    assert loaded.parent.target_key == root.key

    # Act
    await loaded.parent.afetch()

    # Assert
    assert loaded.parent.value.name == "root"


# --- TTL refresh across a reference ---


@pytest_asyncio.fixture
async def owner_with_referee(real_redis_client):
    """Saved owner -> referee pair, with the referee's TTL manually reduced so a
    refresh would be observable as a jump back toward FK_TTL_SECONDS."""
    referee = FkTTLReferee(name="referee")
    await referee.asave()
    owner = FkTTLOwner(title="owner", referee=referee.key)
    await owner.asave()

    await real_redis_client.expire(referee.key, REDUCED_TTL_SECONDS)
    await real_redis_client.expire(owner.key, REDUCED_TTL_SECONDS)
    initial_referee_ttl = await real_redis_client.ttl(referee.key)

    yield owner, referee, initial_referee_ttl

    await owner.adelete()
    await referee.adelete()


@pytest.mark.asyncio
async def test_afetch_does_not_refresh_referenced_model_ttl(
    real_redis_client, owner_with_referee
):
    # Arrange
    owner, referee, initial_referee_ttl = owner_with_referee
    assert initial_referee_ttl <= REDUCED_TTL_SECONDS

    # Act - load the owner and resolve the reference (both are read/fetch ops).
    loaded = await FkTTLOwner.aget(owner.key)
    await loaded.referee.afetch()

    # Assert - the referee does not refresh on read/fetch, so its TTL stays in
    # the reduced window instead of jumping back up to FK_TTL_SECONDS.
    referee_ttl = await real_redis_client.ttl(referee.key)
    assert 0 < referee_ttl <= REDUCED_TTL_SECONDS

    # The owner does refresh on read/fetch, proving the fetch path actually ran.
    owner_ttl = await real_redis_client.ttl(owner.key)
    assert FK_TTL_SECONDS - 2 < owner_ttl <= FK_TTL_SECONDS


