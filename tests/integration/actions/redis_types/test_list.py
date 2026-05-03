from rapyer.types.lst import RedisList
from tests.integration.actions.comprehensive import ComprehensiveTagsOpBase
from tests.integration.actions.read import ReadActionTestBase
from tests.integration.actions.ttl import TTLActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TestListAppend(ComprehensiveTagsOpBase):
    covered_method = RedisList.append

    def create_models(self):
        return [ComprehensiveTestModel()]

    async def perform_action(self, piped):
        piped.tags.append("item1")

    def expected_before(self):
        return []

    def expected_after(self):
        return ["item1"]


class TestListExtend(ComprehensiveTagsOpBase):
    covered_method = RedisList.extend

    def create_models(self):
        return [ComprehensiveTestModel()]

    async def perform_action(self, piped):
        piped.tags.extend(["item1", "item2"])

    def expected_before(self):
        return []

    def expected_after(self):
        return ["item1", "item2"]


class TestRedisListInsert(ComprehensiveTagsOpBase):
    covered_method = RedisList.insert

    def create_models(self):
        return [ComprehensiveTestModel(tags=["first", "last"])]

    async def perform_action(self, piped):
        piped.tags.insert(1, "middle")

    def expected_before(self):
        return ["first", "last"]

    def expected_after(self):
        return ["first", "middle", "last"]


class TestRedisListClear(ComprehensiveTagsOpBase):
    covered_method = RedisList.clear

    def create_models(self):
        return [ComprehensiveTestModel(tags=["tag1", "tag2", "tag3"])]

    async def perform_action(self, piped):
        piped.tags.clear()

    def expected_before(self):
        return ["tag1", "tag2", "tag3"]

    def expected_after(self):
        return []


class TestRedisListRemoveRange(ComprehensiveTagsOpBase):
    covered_method = RedisList.remove_range

    def create_models(self):
        return [ComprehensiveTestModel(tags=["a", "b", "c", "d", "e"])]

    async def perform_action(self, piped):
        piped.tags.remove_range(1, 3)

    def expected_before(self):
        return ["a", "b", "c", "d", "e"]

    def expected_after(self):
        return ["a", "d", "e"]


class TestRedisListSetitem(ComprehensiveTagsOpBase):
    covered_method = RedisList.__setitem__

    def create_models(self):
        return [ComprehensiveTestModel(tags=["first", "second", "third"])]

    async def perform_action(self, piped):
        piped.tags[1] = "modified"

    def expected_before(self):
        return ["first", "second", "third"]

    def expected_after(self):
        return ["first", "modified", "third"]


class TestRedisListIadd(ComprehensiveTagsOpBase):
    covered_method = RedisList.__iadd__

    def create_models(self):
        return [ComprehensiveTestModel(tags=["initial"])]

    async def perform_action(self, piped):
        piped.tags += ["added1", "added2"]

    def expected_before(self):
        return ["initial"]

    def expected_after(self):
        return ["initial", "added1", "added2"]


class TestListAappend(ComprehensiveTagsOpBase, TTLActionTestBase):
    covered_method = RedisList.aappend

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

    def expected_before(self):
        return ["tag1", "tag2"]

    def expected_after(self):
        return []


class TestListApop(ReadActionTestBase, ComprehensiveTagsOpBase, TTLActionTestBase):
    covered_method = RedisList.apop
    skip_pipeline_atomicity = "action returns a value; can't be deferred in a pipeline"

    def create_models(self):
        return [ComprehensiveTestModel(tags=["tag1", "tag2"])]

    async def perform_action(self, piped: ComprehensiveTestModel):
        return await piped.tags.apop()

    def expected_before(self):
        return "tag2"

    def expected_after(self):
        return ["tag1"]
