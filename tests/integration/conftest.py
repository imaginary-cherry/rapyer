import os

import pytest_asyncio
import rapyer

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
    ]

    # Configure Redis client for all models
    for model in redis_models:
        model.Meta.redis = redis_client

    yield redis_client
    await redis_client.aclose()
