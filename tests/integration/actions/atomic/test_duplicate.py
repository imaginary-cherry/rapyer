from rapyer.base import AtomicRedisModel
from tests.integration.actions.create import CreateActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
from tests.integration.functioninality.assertions import assert_atomic_models_equal
from tests.models.collection_types import ComprehensiveTestModel


class TestRapyerAduplicate(UpdateActionTestBase, CreateActionTestBase):
    covered_method = AtomicRedisModel.aduplicate
    model_exists_before_action = False
    skip_stale_mirror_in_pipeline = (
        "atomic aduplicate; no field-level local mirror to corrupt"
    )

    duplicate: ComprehensiveTestModel | None = None

    def models_to_check_ttl(self):
        if self.duplicate is None:
            return []
        return [self.duplicate]

    def create_models(self):
        return [ComprehensiveTestModel(name="original", counter=42, tags=["t1"])]

    async def setup_for_creation(self):
        return await self.setup_data()

    async def perform_action(self, piped):
        self.duplicate = await self.created_models[0].aduplicate()

    async def load_data(self):
        exists = await self.real_redis_client.exists(self.duplicate.key)
        if not exists:
            return None
        return await ComprehensiveTestModel.aget(self.duplicate.key)

    def expected_before(self):
        return None

    async def _assert_is_duplicate(self, loaded):
        await assert_atomic_models_equal(loaded, self.created_models[0])
        assert self.duplicate.key != self.created_models[0].key

    async def assert_after_pipeline(self, loaded):
        await self._assert_is_duplicate(loaded)

    async def assert_action_effect(self, loaded, action_result):
        await self._assert_is_duplicate(loaded)

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.counter += 7919

    def get_target_field(self, m: ComprehensiveTestModel) -> int:
        return int(m.counter)


class TestRapyerAduplicateMany(UpdateActionTestBase, CreateActionTestBase):
    covered_method = AtomicRedisModel.aduplicate_many
    model_exists_before_action = False
    skip_stale_mirror_in_pipeline = (
        "atomic aduplicate_many; no field-level local mirror to corrupt"
    )

    duplicates: list[ComprehensiveTestModel] | None = None

    def duplicates_lst(self):
        return self.duplicates or []

    def models_to_check_ttl(self):
        return self.duplicates_lst()

    def create_models(self):
        return [ComprehensiveTestModel(name="original", counter=42, tags=["t1"])]

    async def setup_for_creation(self):
        return await self.setup_data()

    async def perform_action(self, piped):
        self.duplicates = await self.created_models[0].aduplicate_many(3)

    async def load_data(self):
        results = []
        for dup in self.duplicates_lst():
            exists = await self.real_redis_client.exists(dup.key)
            if not exists:
                results.append(None)
                continue
            results.append(await ComprehensiveTestModel.aget(dup.key))
        return results

    def expected_before(self):
        return [None] * 3

    async def _assert_are_duplicates(self, loaded):
        for model in loaded:
            await assert_atomic_models_equal(model, self.created_models[0])
        all_pks = [self.created_models[0].pk] + [d.pk for d in self.duplicates_lst()]
        assert len(set(all_pks)) == 4

    async def assert_after_pipeline(self, loaded):
        await self._assert_are_duplicates(loaded)

    async def assert_action_effect(self, loaded, action_result):
        await self._assert_are_duplicates(loaded)

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.counter += 7919

    def get_target_field(self, m: ComprehensiveTestModel) -> int:
        return int(m.counter)
