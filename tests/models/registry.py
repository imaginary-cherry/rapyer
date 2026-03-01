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
from tests.models.common import UserWithKeyModel, EventWithDatetimeKeyModel
from tests.models.complex_types import (
    OuterModel,
    InnerRedisModel,
    OuterModelWithRedisNested,
    TestRedisModel,
)
from tests.models.functionality_types import (
    LockSaveTestModel,
    LockUpdateTestModel,
    RichModel,
    AllTypesModel,
)
from tests.models.index_types import (
    ParentWithIndexModel,
    ChildWithParentModel,
    IndexTestModel,
)
from tests.models.inheritance_types import (
    BaseUserModel,
    AdminUserModel,
    DiamondChildModel,
)
from tests.models.pickle_types import ModelWithUnserializableFields
from tests.models.redis_types import (
    RapyerKeyFieldModel,
    ListOfDictsRapyerKeyModel,
    DictOfListsRapyerKeyModel,
)
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
from tests.models.specialized import UserModel
from tests.models.unknown_types import (
    ModelWithStrEnumDefault,
    ModelWithIntEnumDefault,
    ModelWithStrEnumInList,
    ModelWithStrEnumInDict,
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
