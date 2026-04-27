from rapyer.types.dct import RedisDict
from tests.integration.actions.comprehensive import ComprehensiveMetadataOpBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestDictUpdate(ComprehensiveMetadataOpBase):
    covered_method = RedisDict.update

    def create_models(self):
        return [ComprehensiveTestModel()]

    async def perform_action(self, piped):
        piped.metadata.update({"key1": "value1", "key2": "value2"})

    def expected_before(self):
        return {}

    def expected_after(self):
        return {"key1": "value1", "key2": "value2"}


class TestDictSetitem(ComprehensiveMetadataOpBase):
    covered_method = RedisDict.__setitem__

    def create_models(self):
        return [ComprehensiveTestModel()]

    async def perform_action(self, piped):
        piped.metadata["direct_key"] = "direct_value"

    def expected_before(self):
        return {}

    def expected_after(self):
        return {"direct_key": "direct_value"}


class TestRedisDictClear(ComprehensiveMetadataOpBase):
    covered_method = RedisDict.clear

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"key1": "val1", "key2": "val2"})]

    async def perform_action(self, piped):
        piped.metadata.clear()

    def expected_before(self):
        return {"key1": "val1", "key2": "val2"}

    def expected_after(self):
        return {}


class TestDictAsetItem(ComprehensiveMetadataOpBase, TTLActionTestBase):
    covered_method = RedisDict.aset_item

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"existing": "value"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.aset_item("new_key", "new_value")

    def expected_before(self):
        return {"existing": "value"}

    def expected_after(self):
        return {"existing": "value", "new_key": "new_value"}


class TestDictAdelItem(ComprehensiveMetadataOpBase, TTLActionTestBase):
    covered_method = RedisDict.adel_item

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"key1": "value1", "key2": "value2"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.adel_item("key1")

    def expected_before(self):
        return {"key1": "value1", "key2": "value2"}

    def expected_after(self):
        return {"key2": "value2"}


class TestDictAupdate(ComprehensiveMetadataOpBase, TTLActionTestBase):
    covered_method = RedisDict.aupdate

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"existing": "value"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.aupdate(key1="value1", key2="value2")

    def expected_before(self):
        return {"existing": "value"}

    def expected_after(self):
        return {
            "existing": "value",
            "key1": "value1",
            "key2": "value2",
        }


class TestDictAclear(ComprehensiveMetadataOpBase, TTLActionTestBase):
    covered_method = RedisDict.aclear

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"key1": "value1", "key2": "value2"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.aclear()

    def expected_before(self):
        return {"key1": "value1", "key2": "value2"}

    def expected_after(self):
        return {}


class TestDictApop(ComprehensiveMetadataOpBase, TTLActionTestBase):
    covered_method = RedisDict.apop
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(metadata={"key1": "value1", "key2": "value2"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.apop("key1")

    def expected_before(self):
        return {"key1": "value1", "key2": "value2"}

    def expected_after(self):
        return {"key2": "value2"}


class TestDictApopitem(ComprehensiveMetadataOpBase, TTLActionTestBase):
    covered_method = RedisDict.apopitem
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        # Single-entry dict so the popped item is deterministic.
        return [ComprehensiveTestModel(metadata={"only": "value"})]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.metadata.apopitem()

    def expected_before(self):
        return {"only": "value"}

    def expected_after(self):
        return {}
