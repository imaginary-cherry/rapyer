import os
from dataclasses import dataclass
from typing import Generic, TypeVar
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

import rapyer
from rapyer.scripts import register_scripts

REDUCED_TTL_SECONDS = 10

T = TypeVar("T")


@dataclass
class SavedModelWithReducedTTL(Generic[T]):
    model: T
    initial_ttl: int


# Collection types
from tests.models.collection_types import (
    UserListModel,
    ProductListModel,
    IntListModel,
    StrListModel,
    DictListModel,
    BaseModelListModel,
    ListModel,
    IntDictModel,
    StrDictModel,
    DictDictModel,
    BaseModelDictSetitemModel,
    BytesDictModel,
    DatetimeDictModel,
    EnumDictModel,
    AnyDictModel,
    BaseModelDictModel,
    BoolDictModel,
    ListDictModel,
    NestedDictModel,
    DictModel,
    MixedTypesModel,
    PipelineTestModel,
    ComprehensiveTestModel,
    BaseDictMetadataModel,
)

# Common types with key annotations
from tests.models.common import UserWithKeyModel, EventWithDatetimeKeyModel

# Complex types
from tests.models.complex_types import (
    OuterModel,
    InnerRedisModel,
    OuterModelWithRedisNested,
    TestRedisModel,
)

# Functionality types
from tests.models.functionality_types import (
    LockSaveTestModel,
    LockUpdateTestModel,
    RichModel,
    AllTypesModel,
)

# Index types
from tests.models.index_types import ParentWithIndexModel, ChildWithParentModel

# Inheritance types
from tests.models.inheritance_types import (
    BaseUserModel,
    AdminUserModel,
    DiamondChildModel,
)

# Pickle types
from tests.models.pickle_types import ModelWithUnserializableFields

# SafeLoad types
from tests.models.safe_load_types import (
    ModelWithSafeLoadField,
    ModelWithMultipleSafeLoadFields,
    ModelWithMixedFields,
    ModelWithSafeLoadAllConfig,
    ModelWithSafeLoadListOfAny,
    ModelWithSafeLoadDictOfAny,
    ModelWithUnsafeListOfAny,
    ModelWithUnsafeDictOfAny,
)

# Simple types
from tests.models.simple_types import (
    IntModel,
    FloatModel,
    BoolModel,
    StrModel,
    BytesModel,
    DatetimeModel,
    DatetimeListModel,
    DatetimeDictModel,
    UserModelWithTTL,
    UserModelWithoutTTL,
    TaskModel,
    NoneTestModel,
    TTLRefreshTestModel,
    TTLRefreshDisabledModel,
)

# Specialized types
from tests.models.specialized import UserModel

# Unknown types (JSON serializable enums)
from tests.models.unknown_types import (
    ModelWithStrEnumDefault,
    ModelWithIntEnumDefault,
    ModelWithStrEnumInList,
    ModelWithStrEnumInDict,
)


@pytest_asyncio.fixture
async def redis_client():
    meta_redis = rapyer.AtomicRedisModel.Meta.redis
    db_num = os.getenv("REDIS_DB", "0")
    redis = meta_redis.from_url(
        f"redis://localhost:6370/{db_num}", decode_responses=True
    )
    await redis.flushdb()
    yield redis
    await redis.flushdb()


@pytest_asyncio.fixture(autouse=True)
async def real_redis_client(redis_client):
    # All Redis models that need the client configured
    redis_models = [
        # Collection types - List models
        UserListModel,
        ProductListModel,
        IntListModel,
        StrListModel,
        DictListModel,
        BaseModelListModel,
        ListModel,
        # Collection types - Dict models
        BaseDictMetadataModel,
        IntDictModel,
        StrDictModel,
        DictDictModel,
        BaseModelDictSetitemModel,
        BytesDictModel,
        DatetimeDictModel,
        EnumDictModel,
        AnyDictModel,
        BaseModelDictModel,
        BoolDictModel,
        ListDictModel,
        NestedDictModel,
        DictModel,
        # Collection types - Mixed and pipeline models
        MixedTypesModel,
        PipelineTestModel,
        ComprehensiveTestModel,
        # Simple types
        IntModel,
        FloatModel,
        BoolModel,
        StrModel,
        BytesModel,
        DatetimeModel,
        DatetimeListModel,
        DatetimeDictModel,
        UserModelWithTTL,
        UserModelWithoutTTL,
        TaskModel,
        NoneTestModel,
        TTLRefreshTestModel,
        TTLRefreshDisabledModel,
        # Functionality types
        LockSaveTestModel,
        LockUpdateTestModel,
        RichModel,
        AllTypesModel,
        # Specialized types
        UserModel,
        # Pickle types
        ModelWithUnserializableFields,
        # SafeLoad types
        ModelWithSafeLoadField,
        ModelWithMultipleSafeLoadFields,
        ModelWithMixedFields,
        ModelWithSafeLoadAllConfig,
        ModelWithSafeLoadListOfAny,
        ModelWithSafeLoadDictOfAny,
        ModelWithUnsafeListOfAny,
        ModelWithUnsafeDictOfAny,
        # Inheritance types
        BaseUserModel,
        AdminUserModel,
        DiamondChildModel,
        # Complex types
        OuterModel,
        InnerRedisModel,
        OuterModelWithRedisNested,
        TestRedisModel,
        # Common types with key annotations
        UserWithKeyModel,
        EventWithDatetimeKeyModel,
        # Index types
        ParentWithIndexModel,
        ChildWithParentModel,
        # Unknown types (JSON serializable enums)
        ModelWithStrEnumDefault,
        ModelWithIntEnumDefault,
        ModelWithStrEnumInList,
        ModelWithStrEnumInDict,
    ]

    # Configure Redis client for all models
    for model in redis_models:
        model.Meta.redis = redis_client

    # Register Lua scripts
    await register_scripts(redis_client)

    yield redis_client

    await redis_client.aclose()


@pytest_asyncio.fixture
async def saved_model_with_reduced_ttl(real_redis_client):
    model = TTLRefreshTestModel(
        name="ttl_test",
        age=25,
        score=10.5,
        tags=["tag1", "tag2"],
        settings={"key1": "value1", "key2": "value2"},
    )
    await model.asave()
    await real_redis_client.expire(model.key, REDUCED_TTL_SECONDS)
    initial_ttl = await real_redis_client.ttl(model.key)

    yield SavedModelWithReducedTTL(model=model, initial_ttl=initial_ttl)

    await model.adelete()


@pytest_asyncio.fixture
async def flush_scripts(real_redis_client):
    await real_redis_client.execute_command("SCRIPT", "FLUSH")
    yield


@pytest.fixture
def disable_base_noscript_recovery():
    with patch("rapyer.base.handle_noscript_error", new_callable=AsyncMock):
        yield


@pytest.fixture
def disable_registry_noscript_recovery():
    with patch("rapyer.scripts.registry.handle_noscript_error", new_callable=AsyncMock):
        yield


@pytest_asyncio.fixture
async def saved_no_refresh_model_with_reduced_ttl(real_redis_client):
    model = TTLRefreshDisabledModel(
        name="ttl_no_refresh_test",
        age=25,
        score=10.5,
        tags=["tag1", "tag2"],
        settings={"key1": "value1", "key2": "value2"},
    )
    await model.asave()
    await real_redis_client.expire(model.key, REDUCED_TTL_SECONDS)
    initial_ttl = await real_redis_client.ttl(model.key)

    yield SavedModelWithReducedTTL(model=model, initial_ttl=initial_ttl)

    await model.adelete()
