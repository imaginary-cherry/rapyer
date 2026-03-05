from tests.models.collection_types import (
    AnyDictModel,
    BaseDictMetadataModel,
    BaseModelDictModel,
    BaseModelDictSetitemModel,
    BaseModelListModel,
    BoolDictModel,
    BytesDictModel,
    ComprehensiveTestModel,
    DictDictModel,
    DictListModel,
    DictModel,
    EnumDictModel,
    IntDictModel,
    IntListModel,
    ListDictModel,
    ListModel,
    MixedTypesModel,
    NestedDictModel,
    PipelineTestModel,
    ProductListModel,
    StrDictModel,
    StrListModel,
    UserListModel,
)
from tests.models.common import EventWithDatetimeKeyModel, UserWithKeyModel
from tests.models.complex_types import (
    InnerRedisModel,
    OuterModel,
    OuterModelWithRedisNested,
    TestRedisModel,
)
from tests.models.functionality_types import (
    AllTypesModel,
    LockSaveTestModel,
    LockUpdateTestModel,
    RichModel,
)
from tests.models.index_types import (
    ChildWithParentModel,
    IndexTestModel,
    ParentWithIndexModel,
)
from tests.models.inheritance_types import (
    AdminUserModel,
    BaseUserModel,
    DiamondChildModel,
)
from tests.models.pickle_types import ModelWithUnserializableFields
from tests.models.redis_types import (
    DictOfListsRapyerKeyModel,
    ListOfDictsRapyerKeyModel,
    RapyerKeyFieldModel,
)
from tests.models.safe_load_types import (
    ModelWithMixedFields,
    ModelWithMultipleSafeLoadFields,
    ModelWithSafeLoadAllConfig,
    ModelWithSafeLoadDictOfAny,
    ModelWithSafeLoadField,
    ModelWithSafeLoadListOfAny,
    ModelWithUnsafeDictOfAny,
    ModelWithUnsafeListOfAny,
)
from tests.models.simple_types import (
    BoolModel,
    BytesModel,
    DatetimeDictModel,
    DatetimeListModel,
    DatetimeModel,
    FloatModel,
    IntModel,
    NoneTestModel,
    StrModel,
    TaskModel,
    TTLRefreshDisabledModel,
    TTLRefreshTestModel,
    UserModelWithoutTTL,
    UserModelWithTTL,
)
from tests.models.specialized import UserModel
from tests.models.unknown_types import (
    ModelWithIntEnumDefault,
    ModelWithStrEnumDefault,
    ModelWithStrEnumInDict,
    ModelWithStrEnumInList,
)

TESTED_REDIS_MODELS = [
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
    IndexTestModel,
    # Unknown types (JSON serializable enums)
    ModelWithStrEnumDefault,
    ModelWithIntEnumDefault,
    ModelWithStrEnumInList,
    ModelWithStrEnumInDict,
    # Redis types
    RapyerKeyFieldModel,
    ListOfDictsRapyerKeyModel,
    DictOfListsRapyerKeyModel,
]
