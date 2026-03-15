import pytest

import rapyer
from tests.models.common import UserWithKeyModel
from tests.models.simple_types import IntModel, StrModel


@pytest.mark.asyncio
async def test_aexists__returns_true_after_save(setup_fake_redis_for_models):
    model = StrModel(name="test_user", description="test description")
    await model.asave()

    result = await StrModel.aexists(model.key)

    assert result is True


@pytest.mark.asyncio
async def test_aexists__returns_false_for_missing_key(setup_fake_redis_for_models):
    result = await StrModel.aexists("StrModel:nonexistent_key")

    assert result is False


@pytest.mark.asyncio
async def test_aexists__key_model_without_prefix(setup_fake_redis_for_models):
    model = UserWithKeyModel(
        user_id="exists_test_key",
        name="Key User",
        email="keyuser@example.com",
        age=32,
    )
    await model.asave()

    result = await UserWithKeyModel.aexists("exists_test_key")

    assert result is True


@pytest.mark.asyncio
async def test_aexists__returns_false_after_delete(setup_fake_redis_for_models):
    model = IntModel(count=42, score=100)
    await model.asave()

    assert await IntModel.aexists(model.key) is True

    await model.adelete()

    assert await IntModel.aexists(model.key) is False


@pytest.mark.asyncio
async def test_rapyer_aexists__module_level_existing_key(setup_fake_redis_for_models):
    model = StrModel(name="module_test", description="module level")
    await model.asave()

    result = await rapyer.aexists(model.key)

    assert result is True


@pytest.mark.asyncio
async def test_rapyer_aexists__module_level_unknown_class(setup_fake_redis_for_models):
    result = await rapyer.aexists("UnknownClass:123")

    assert result is False
