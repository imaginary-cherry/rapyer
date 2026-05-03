from benchmarks.base import AsyncBenchmarkTest
from tests.models.collection_types import SimpleListModel
from tests.models.complex_types import OuterModel
from tests.models.simple_types import StrModel


class TestSetattrSimpleField(AsyncBenchmarkTest):
    async def setup(self):
        return StrModel(name="initial")

    async def action(self, model):
        model.name = "updated"


class TestSetattrListItem(AsyncBenchmarkTest):
    async def setup(self):
        return SimpleListModel(items=["initial"])

    async def action(self, model):
        model.items[0] = "updated"


class TestSetattrNestedField(AsyncBenchmarkTest):
    async def setup(self):
        return OuterModel()

    async def action(self, model):
        model.middle_model.tags = ["new"]
