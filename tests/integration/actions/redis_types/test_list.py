from rapyer.types.lst import RedisList
from tests.integration.actions.comprehensive import ComprehensiveTagsOpBase
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.actions.sync_action import SyncActionTestBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestListAppend(ComprehensiveTagsOpBase, SyncActionTestBase):
    covered_method = RedisList.append
    skip_stale_mirror_in_pipeline = "APPEND action; native list.append never raises"
    skip_sync_native_raises_on_corruption = "native list.append never raises"

    def create_models(self):
        return [ComprehensiveTestModel()]

    async def perform_action(self, piped):
        piped.tags.append("item1")

    def apply_native_action(self, native: list) -> list:
        native.append("item1")
        return native

    def expected_before(self):
        return []

    def expected_after(self):
        return ["item1"]


class TestListExtend(ComprehensiveTagsOpBase, SyncActionTestBase):
    covered_method = RedisList.extend
    skip_stale_mirror_in_pipeline = "APPEND action; native list.extend never raises"
    skip_sync_native_raises_on_corruption = "native list.extend never raises"

    def create_models(self):
        return [ComprehensiveTestModel()]

    async def perform_action(self, piped):
        piped.tags.extend(["item1", "item2"])

    def apply_native_action(self, native: list) -> list:
        native.extend(["item1", "item2"])
        return native

    def expected_before(self):
        return []

    def expected_after(self):
        return ["item1", "item2"]


class TestRedisListInsert(ComprehensiveTagsOpBase, SyncActionTestBase):
    covered_method = RedisList.insert
    skip_stale_mirror_in_pipeline = "APPEND action; native list.insert never raises"
    skip_sync_native_raises_on_corruption = "native list.insert never raises"

    def create_models(self):
        return [ComprehensiveTestModel(tags=["first", "last"])]

    async def perform_action(self, piped):
        piped.tags.insert(1, "middle")

    def apply_native_action(self, native: list) -> list:
        native.insert(1, "middle")
        return native

    def expected_before(self):
        return ["first", "last"]

    def expected_after(self):
        return ["first", "middle", "last"]


class TestRedisListClear(ComprehensiveTagsOpBase, SyncActionTestBase):
    covered_method = RedisList.clear
    skip_sync_native_raises_on_corruption = "native list.clear is idempotent"

    def create_models(self):
        return [ComprehensiveTestModel(tags=["tag1", "tag2", "tag3"])]

    async def perform_action(self, piped):
        piped.tags.clear()

    def apply_native_action(self, native: list) -> list:
        native.clear()
        return native

    def expected_before(self):
        return ["tag1", "tag2", "tag3"]

    def expected_after(self):
        return []


class TestRedisListRemoveRange(ComprehensiveTagsOpBase):
    # remove_range is pipeline-only; it does not mutate the local mirror
    # outside an open pipeline, so it is exempt from COVER_SYNC_NATIVE_EFFECT.
    covered_method = RedisList.remove_range
    skip_stale_mirror_in_pipeline = (
        "remove_range is pipeline-only; no local mirror to corrupt outside a pipeline"
    )

    def create_models(self):
        return [ComprehensiveTestModel(tags=["a", "b", "c", "d", "e"])]

    async def perform_action(self, piped):
        piped.tags.remove_range(1, 3)

    def expected_before(self):
        return ["a", "b", "c", "d", "e"]

    def expected_after(self):
        return ["a", "d", "e"]


class TestRedisListSetitem(ComprehensiveTagsOpBase, SyncActionTestBase):
    covered_method = RedisList.__setitem__
    skip_stale_mirror_in_pipeline = (
        "UPDATE action (no ERASE); native list[i]=x never raises on a valid index"
    )
    skip_sync_native_raises_on_corruption = "native list[i]=x never raises"

    def create_models(self):
        return [ComprehensiveTestModel(tags=["first", "second", "third"])]

    async def perform_action(self, piped):
        piped.tags[1] = "modified"

    def apply_native_action(self, native: list) -> list:
        native[1] = "modified"
        return native

    def expected_before(self):
        return ["first", "second", "third"]

    def expected_after(self):
        return ["first", "modified", "third"]


class TestRedisListIadd(ComprehensiveTagsOpBase, SyncActionTestBase):
    covered_method = RedisList.__iadd__
    skip_stale_mirror_in_pipeline = "APPEND action; native list += never raises"
    skip_sync_native_raises_on_corruption = "native list += never raises"

    def create_models(self):
        return [ComprehensiveTestModel(tags=["initial"])]

    async def perform_action(self, piped):
        piped.tags += ["added1", "added2"]

    def apply_native_action(self, native: list) -> list:
        native += ["added1", "added2"]
        return native

    def expected_before(self):
        return ["initial"]

    def expected_after(self):
        return ["initial", "added1", "added2"]


class TestListAappend(ComprehensiveTagsOpBase, TTLActionTestBase):
    covered_method = RedisList.aappend
    skip_stale_mirror_in_pipeline = "APPEND action; native list.append never raises"

    def create_models(self):
        return [ComprehensiveTestModel(tags=["initial"])]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tags.aappend("new_tag")

    def expected_before(self):
        return ["initial"]

    def expected_after(self):
        return ["initial", "new_tag"]


class TestListAextend(ComprehensiveTagsOpBase, TTLActionTestBase):
    covered_method = RedisList.aextend
    skip_stale_mirror_in_pipeline = "APPEND action; native list.extend never raises"

    def create_models(self):
        return [ComprehensiveTestModel(tags=["initial"])]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tags.aextend(["tag1", "tag2"])

    def expected_before(self):
        return ["initial"]

    def expected_after(self):
        return ["initial", "tag1", "tag2"]


class TestListAinsert(ComprehensiveTagsOpBase, TTLActionTestBase):
    covered_method = RedisList.ainsert
    skip_stale_mirror_in_pipeline = "APPEND action; native list.insert never raises"

    def create_models(self):
        return [ComprehensiveTestModel(tags=["first", "last"])]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tags.ainsert(1, "middle")

    def expected_before(self):
        return ["first", "last"]

    def expected_after(self):
        return ["first", "middle", "last"]


class TestListAclear(ComprehensiveTagsOpBase, TTLActionTestBase):
    covered_method = RedisList.aclear

    def create_models(self):
        return [ComprehensiveTestModel(tags=["tag1", "tag2"])]

    async def perform_action(self, piped: ComprehensiveTestModel):
        await piped.tags.aclear()

    def corrupt_local_mirror(self, m: ComprehensiveTestModel) -> None:
        list.clear(m.tags)

    def expected_before(self):
        return ["tag1", "tag2"]

    def expected_after(self):
        return []


class TestListApop(ReadActionTestBase, ComprehensiveTagsOpBase, TTLActionTestBase):
    covered_method = RedisList.apop
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"
    skip_stale_mirror_in_pipeline = None  # apop is ERASE — opt back in

    def create_models(self):
        return [ComprehensiveTestModel(tags=["tag1", "tag2"])]

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await piped.tags.apop()

    def expected_before(self):
        return "tag2"

    def expected_after(self):
        return ["tag1"]
