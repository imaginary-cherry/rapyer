from abc import ABC
from typing import ClassVar

import rapyer
from rapyer.types.redis_set import RedisSet
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.actions.sync_action import SyncActionTestBase
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
        return [model.key, model.container.labels.special_key]

    async def setup_data(self):
        models = await super().setup_data()
        for inst in models:
            await inst.container.labels.aadd_many(self.initial_items)
        return models

    async def load_data(self):
        return frozenset(
            await self.real_redis_client.smembers(
                self.created_models[0].container.labels.special_key
            )
        )

    def expected_before(self):
        return INITIAL_SERIALIZED

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.container.labels.add("__local_marker__")

    def get_target_field(self, m: ComprehensiveTestModel) -> set:
        return set(m.container.labels)

    def corrupt_local_mirror(self, m: ComprehensiveTestModel) -> None:
        # Drop the value most ERASE-style actions in this hierarchy target.
        set.discard(m.container.labels, "beta")


class TestSetAadd(RedisSetActionBase):
    covered_method = RedisSet.aadd

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.container.labels.aadd("delta")

    def expected_after(self):
        return INITIAL_SERIALIZED | {'"delta"'}


class TestSetAaddMany(RedisSetActionBase):
    covered_method = RedisSet.aadd_many

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.container.labels.aadd_many(["delta", "epsilon"])

    def expected_after(self):
        return INITIAL_SERIALIZED | {'"delta"', '"epsilon"'}


class TestSetAremove(RedisSetActionBase):
    covered_method = RedisSet.aremove

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.container.labels.aremove("beta")

    def expected_after(self):
        return INITIAL_SERIALIZED - {'"beta"'}


class TestSetAclear(RedisSetActionBase):
    covered_method = RedisSet.aclear

    def ttl_keys(self, model):
        # The special key is deleted by aclear, so don't assert its TTL.
        return [model.key]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.container.labels.aclear()

    def expected_after(self):
        return frozenset()


class TestSetApop(ReadActionTestBase, RedisSetActionBase):
    covered_method = RedisSet.apop
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].container.labels.apop()

    def expected_before(self):
        return set(INITIAL_ITEMS)

    def corrupt_local_mirror(self, m: ComprehensiveTestModel) -> None:
        # Wipe the mirror: native set.pop() would raise, but apop() still returns from Redis.
        set.clear(m.container.labels)

    async def assert_after_pipeline(self, loaded):
        # apop's choice is non-deterministic, so only check Redis shrank by one and stayed a subset.
        assert len(loaded) == len(INITIAL_ITEMS) - 1
        assert loaded <= INITIAL_SERIALIZED

    async def assert_action_effect(self, loaded, action_result):
        expected = self.expected_read_output()
        assert (
            action_result in expected
        ), f"Action returned {action_result!r}; expected one of {expected!r}"


class TestSetAcontains(ReadActionTestBase, RedisSetActionBase):
    covered_method = RedisSet.acontains
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"
    skip_stale_mirror_in_pipeline = "pure read; no local-mirror failure mode"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].container.labels.acontains("alpha")

    def expected_before(self):
        return True


class TestSetAmembers(ReadActionTestBase, RedisSetActionBase):
    covered_method = RedisSet.amembers
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"
    skip_stale_mirror_in_pipeline = "pure read; no local-mirror failure mode"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].container.labels.amembers()

    def expected_before(self):
        return set(INITIAL_ITEMS)


class TestSetAsize(ReadActionTestBase, RedisSetActionBase):
    covered_method = RedisSet.asize
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"
    skip_stale_mirror_in_pipeline = "pure read; no local-mirror failure mode"

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].container.labels.asize()

    def expected_before(self):
        return len(INITIAL_ITEMS)


class TwoSetActionBase(ReadActionTestBase, RedisSetActionBase, ABC):
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"
    skip_stale_mirror_in_pipeline = (
        "multi-set read; server-side only, no local-mirror dependency"
    )
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
        await models[0].container.labels.aadd_many(self.initial_items)
        await models[1].container.labels.aadd_many(self.other_items)
        return models


class TestSetAunion(TwoSetActionBase):
    covered_method = RedisSet.aunion

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].container.labels.aunion(
            self.created_models[1].container.labels
        )

    def expected_before(self):
        return set(self.initial_items) | set(self.other_items)


class TestSetAintersect(TwoSetActionBase):
    covered_method = RedisSet.aintersect

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].container.labels.aintersect(
            self.created_models[1].container.labels
        )

    def expected_before(self):
        return set(self.initial_items) & set(self.other_items)


class TestSetAdifference(TwoSetActionBase):
    covered_method = RedisSet.adifference

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await self.created_models[0].container.labels.adifference(
            self.created_models[1].container.labels
        )

    def expected_before(self):
        return set(self.initial_items) - set(self.other_items)


class RedisSetSyncActionBase(UpdateActionTestBase, SyncActionTestBase, ABC):
    """
    Sync set methods queue Redis ops onto an open pipeline; outside a
    pipeline they only mutate the local mirror. They aren't async, so TTL
    refresh / action-effect coverage doesn't apply — pipeline atomicity and
    no-clobber are what we need.
    """

    initial_items: ClassVar[list[str]] = INITIAL_ITEMS

    def create_models(self):
        return [ComprehensiveTestModel(name="set_sync_test")]

    async def setup_data(self):
        models = await super().setup_data()
        for inst in models:
            await inst.container.labels.aadd_many(self.initial_items)
        return models

    async def load_data(self):
        return frozenset(
            await self.real_redis_client.smembers(
                self.created_models[0].container.labels.special_key
            )
        )

    def expected_before(self):
        return INITIAL_SERIALIZED

    def local_mutate_target_field(self, m: ComprehensiveTestModel) -> None:
        m.container.labels.add("__local_marker__")

    def get_target_field(self, m: ComprehensiveTestModel) -> set:
        return set(m.container.labels)

    def corrupt_local_mirror(self, m: ComprehensiveTestModel) -> None:
        set.discard(m.container.labels, "beta")


class TestSetAdd(RedisSetSyncActionBase):
    covered_method = RedisSet.add
    skip_sync_native_raises_on_corruption = "native set.add never raises"

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels.add("delta")

    def apply_native_action(self, native: set) -> set:
        native.add("delta")
        return native

    def expected_after(self):
        return INITIAL_SERIALIZED | {'"delta"'}


class TestSetUpdate(RedisSetSyncActionBase):
    covered_method = RedisSet.update
    skip_sync_native_raises_on_corruption = "native set.update never raises"

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels.update(["delta", "epsilon"])

    def apply_native_action(self, native: set) -> set:
        native.update(["delta", "epsilon"])
        return native

    def expected_after(self):
        return INITIAL_SERIALIZED | {'"delta"', '"epsilon"'}


class TestSetRemove(RedisSetSyncActionBase):
    covered_method = RedisSet.remove

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels.remove("beta")

    def apply_native_action(self, native: set) -> set:
        native.remove("beta")
        return native

    def expected_after(self):
        return INITIAL_SERIALIZED - {'"beta"'}


class TestSetDiscard(RedisSetSyncActionBase):
    covered_method = RedisSet.discard
    skip_sync_native_raises_on_corruption = "native set.discard never raises"

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels.discard("beta")

    def apply_native_action(self, native: set) -> set:
        native.discard("beta")
        return native

    def expected_after(self):
        return INITIAL_SERIALIZED - {'"beta"'}


class TestSetClear(RedisSetSyncActionBase):
    covered_method = RedisSet.clear
    skip_sync_native_raises_on_corruption = "native set.clear is idempotent"

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels.clear()

    def apply_native_action(self, native: set) -> set:
        native.clear()
        return native

    def expected_after(self):
        return frozenset()


class TestSetDifferenceUpdate(RedisSetSyncActionBase):
    covered_method = RedisSet.difference_update
    skip_sync_native_raises_on_corruption = "native set.difference_update never raises"

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels.difference_update({"alpha"})

    def apply_native_action(self, native: set) -> set:
        native.difference_update({"alpha"})
        return native

    def expected_after(self):
        return INITIAL_SERIALIZED - {'"alpha"'}


class TestSetIntersectionUpdate(RedisSetSyncActionBase):
    covered_method = RedisSet.intersection_update
    skip_sync_native_raises_on_corruption = (
        "native set.intersection_update never raises"
    )

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels.intersection_update({"alpha", "delta"})

    def apply_native_action(self, native: set) -> set:
        native.intersection_update({"alpha", "delta"})
        return native

    def expected_after(self):
        return frozenset({'"alpha"'})


class TestSetSymmetricDifferenceUpdate(RedisSetSyncActionBase):
    covered_method = RedisSet.symmetric_difference_update
    skip_sync_native_raises_on_corruption = (
        "native set.symmetric_difference_update never raises"
    )

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels.symmetric_difference_update({"alpha", "delta"})

    def apply_native_action(self, native: set) -> set:
        native.symmetric_difference_update({"alpha", "delta"})
        return native

    def expected_after(self):
        return (INITIAL_SERIALIZED - {'"alpha"'}) | {'"delta"'}


# --- In-place operators ---------------------------------------------------


class TestSetIor(RedisSetSyncActionBase):
    covered_method = RedisSet.__ior__
    skip_sync_native_raises_on_corruption = "native set |= never raises"

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels |= {"delta", "epsilon"}

    def apply_native_action(self, native: set) -> set:
        native |= {"delta", "epsilon"}
        return native

    def expected_after(self):
        return INITIAL_SERIALIZED | {'"delta"', '"epsilon"'}


class TestSetIand(RedisSetSyncActionBase):
    covered_method = RedisSet.__iand__
    skip_sync_native_raises_on_corruption = "native set &= never raises"

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels &= {"alpha", "delta"}

    def apply_native_action(self, native: set) -> set:
        native &= {"alpha", "delta"}
        return native

    def expected_after(self):
        return frozenset({'"alpha"'})


class TestSetIsub(RedisSetSyncActionBase):
    covered_method = RedisSet.__isub__
    skip_sync_native_raises_on_corruption = "native set -= never raises"

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels -= {"alpha"}

    def apply_native_action(self, native: set) -> set:
        native -= {"alpha"}
        return native

    def expected_after(self):
        return INITIAL_SERIALIZED - {'"alpha"'}


class TestSetIxor(RedisSetSyncActionBase):
    covered_method = RedisSet.__ixor__
    skip_sync_native_raises_on_corruption = "native set ^= never raises"

    async def perform_action(self, piped: ComprehensiveTestModel):
        piped.container.labels ^= {"alpha", "delta"}

    def apply_native_action(self, native: set) -> set:
        native ^= {"alpha", "delta"}
        return native

    def expected_after(self):
        return (INITIAL_SERIALIZED - {'"alpha"'}) | {'"delta"'}
