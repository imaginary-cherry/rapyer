from abc import ABC
from typing import ClassVar

import rapyer
from rapyer.types.redis_set import RedisSet
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel

INITIAL_ITEMS: list[str] = ["alpha", "beta", "gamma"]
INITIAL_SERIALIZED: frozenset[str] = frozenset({'"alpha"', '"beta"', '"gamma"'})


class RedisSetActionBase(UpdateActionTestBase, TTLActionTestBase, ABC):
    initial_items: ClassVar[list[str]] = INITIAL_ITEMS

    def create_models(self):
        return [ComprehensiveTestModel(name="set_test")]

    def ttl_keys(self, model: ComprehensiveTestModel):
        return [model.key, model.labels.special_key]

    async def setup_data(self):
        models = await super().setup_data()
        for inst in models:
            await inst.labels.aadd_many(self.initial_items)
        return models

    async def load_data(self):
        return frozenset(
            await self.real_redis_client.smembers(
                self.created_models[0].labels.special_key
            )
        )

    def expected_before(self):
        return INITIAL_SERIALIZED

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.labels.add("__local_marker__")

    def get_target_field(self, m: ComprehensiveTestModel) -> set:
        return set(m.labels)


class TestSetAadd(RedisSetActionBase):
    covered_method = RedisSet.aadd

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.labels.aadd("delta")

    def expected_after(self):
        return INITIAL_SERIALIZED | {'"delta"'}


class TestSetAaddMany(RedisSetActionBase):
    covered_method = RedisSet.aadd_many

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.labels.aadd_many(["delta", "epsilon"])

    def expected_after(self):
        return INITIAL_SERIALIZED | {'"delta"', '"epsilon"'}


class TestSetAremove(RedisSetActionBase):
    covered_method = RedisSet.aremove

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.labels.aremove("beta")

    def expected_after(self):
        return INITIAL_SERIALIZED - {'"beta"'}


class TestSetAclear(RedisSetActionBase):
    covered_method = RedisSet.aclear

    def ttl_keys(self, model):
        # The special key is deleted by aclear, so don't assert its TTL.
        return [model.key]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.labels.aclear()

    def expected_after(self):
        return frozenset()


class TestSetApop(ReadActionTestBase, RedisSetActionBase):
    covered_method = RedisSet.apop
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].labels.apop()

    def expected_before(self):
        return set(INITIAL_ITEMS)

    def assert_action_effect(self, loaded, action_result):
        expected = self.expected_read_output()
        assert (
            action_result in expected
        ), f"Action returned {action_result!r}; expected one of {expected!r}"


class TestSetAcontains(ReadActionTestBase, RedisSetActionBase):
    covered_method = RedisSet.acontains
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].labels.acontains("alpha")

    def expected_before(self):
        return True


class TestSetAmembers(ReadActionTestBase, RedisSetActionBase):
    covered_method = RedisSet.amembers
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].labels.amembers()

    def expected_before(self):
        return set(INITIAL_ITEMS)


class TestSetAsize(ReadActionTestBase, RedisSetActionBase):
    covered_method = RedisSet.asize
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].labels.asize()

    def expected_before(self):
        return len(INITIAL_ITEMS)


class _TwoSetActionBase(ReadActionTestBase, RedisSetActionBase, ABC):
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"
    other_items: ClassVar[list[str]] = ["gamma", "delta", "epsilon"]

    def create_models(self):
        return [
            ComprehensiveTestModel(name="set_a"),
            ComprehensiveTestModel(name="set_b"),
        ]

    def models_to_check_ttl(self):
        # TTL behavior is checked for the model on which the action is invoked.
        return [self.created_models[0]]

    async def setup_data(self):
        models = self.create_models()
        await rapyer.ainsert(*models)
        await models[0].labels.aadd_many(self.initial_items)
        await models[1].labels.aadd_many(self.other_items)
        return models


class TestSetAunion(_TwoSetActionBase):
    covered_method = RedisSet.aunion

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].labels.aunion(self.created_models[1].labels)

    def expected_before(self):
        return set(self.initial_items) | set(self.other_items)


class TestSetAintersect(_TwoSetActionBase):
    covered_method = RedisSet.aintersect

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].labels.aintersect(
            self.created_models[1].labels
        )

    def expected_before(self):
        return set(self.initial_items) & set(self.other_items)


class TestSetAdifference(_TwoSetActionBase):
    covered_method = RedisSet.adifference

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].labels.adifference(
            self.created_models[1].labels
        )

    def expected_before(self):
        return set(self.initial_items) - set(self.other_items)


class RedisSetSyncActionBase(UpdateActionTestBase, ABC):
    """Sync set methods queue Redis ops onto an open pipeline; outside a
    pipeline they only mutate the local mirror. They aren't async, so TTL
    refresh / action-effect coverage doesn't apply — pipeline atomicity and
    no-clobber are what we need."""

    initial_items: ClassVar[list[str]] = INITIAL_ITEMS

    def create_models(self):
        return [ComprehensiveTestModel(name="set_sync_test")]

    async def setup_data(self):
        models = await super().setup_data()
        for inst in models:
            await inst.labels.aadd_many(self.initial_items)
        return models

    async def load_data(self):
        return frozenset(
            await self.real_redis_client.smembers(
                self.created_models[0].labels.special_key
            )
        )

    def expected_before(self):
        return INITIAL_SERIALIZED

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.labels.add("__local_marker__")

    def get_target_field(self, m: ComprehensiveTestModel) -> set:
        return set(m.labels)


class TestSetAdd(RedisSetSyncActionBase):
    covered_method = RedisSet.add

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.labels.add("delta")

    def expected_after(self):
        return INITIAL_SERIALIZED | {'"delta"'}


class TestSetUpdate(RedisSetSyncActionBase):
    covered_method = RedisSet.update

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.labels.update(["delta", "epsilon"])

    def expected_after(self):
        return INITIAL_SERIALIZED | {'"delta"', '"epsilon"'}


class TestSetRemove(RedisSetSyncActionBase):
    covered_method = RedisSet.remove

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.labels.remove("beta")

    def expected_after(self):
        return INITIAL_SERIALIZED - {'"beta"'}


class TestSetDiscard(RedisSetSyncActionBase):
    covered_method = RedisSet.discard

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.labels.discard("beta")

    def expected_after(self):
        return INITIAL_SERIALIZED - {'"beta"'}


class TestSetClear(RedisSetSyncActionBase):
    covered_method = RedisSet.clear

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.labels.clear()

    def expected_after(self):
        return frozenset()


class TestSetDifferenceUpdate(RedisSetSyncActionBase):
    covered_method = RedisSet.difference_update

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.labels.difference_update({"alpha"})

    def expected_after(self):
        return INITIAL_SERIALIZED - {'"alpha"'}


class TestSetIntersectionUpdate(RedisSetSyncActionBase):
    covered_method = RedisSet.intersection_update

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.labels.intersection_update({"alpha", "delta"})

    def expected_after(self):
        return frozenset({'"alpha"'})


class TestSetSymmetricDifferenceUpdate(RedisSetSyncActionBase):
    covered_method = RedisSet.symmetric_difference_update

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.labels.symmetric_difference_update({"alpha", "delta"})

    def expected_after(self):
        return (INITIAL_SERIALIZED - {'"alpha"'}) | {'"delta"'}
