import rapyer
from rapyer.base import AtomicRedisModel
from tests.integration.actions.create import CreateActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
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
        models = self.create_models()
        await rapyer.ainsert(*models)
        return models

    async def perform_action(self, piped):
        self.duplicate = await self.created_models[0].aduplicate()

    async def load_data(self):
        exists = await self.real_redis_client.exists(self.duplicate.key)
        if not exists:
            return 0, None, None, None
        loaded = await ComprehensiveTestModel.aget(self.duplicate.key)
        return 1, loaded.name, loaded.counter, loaded.tags

    def expected_before(self):
        return 0, None, None, None

    def expected_after(self):
        return 1, "original", 42, ["t1"]

    def assert_after_pipeline(self, loaded):
        super().assert_after_pipeline(loaded)
        assert self.duplicate.key != self.created_models[0].key

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
        models = self.create_models()
        await rapyer.ainsert(*models)
        return models

    async def perform_action(self, piped):
        self.duplicates = await self.created_models[0].aduplicate_many(3)

    async def load_data(self):
        results = []
        for dup in self.duplicates_lst():
            exists = await self.real_redis_client.exists(dup.key)
            if not exists:
                results.append((0, None, None, None))
                continue
            loaded = await ComprehensiveTestModel.aget(dup.key)
            results.append((1, loaded.name, loaded.counter, loaded.tags))
        return results

    def expected_before(self):
        return [(0, None, None, None)] * 3

    def expected_after(self):
        return [(1, "original", 42, ["t1"])] * 3

    def assert_after_pipeline(self, loaded):
        super().assert_after_pipeline(loaded)
        all_pks = [self.created_models[0].pk] + [d.pk for d in self.duplicates_lst()]
        assert len(set(all_pks)) == 4

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.counter += 7919

    def get_target_field(self, m: ComprehensiveTestModel) -> int:
        return int(m.counter)
