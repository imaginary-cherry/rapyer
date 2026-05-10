from benchmarks.base import AsyncBenchmarkTest, TTLMode
from tests.models.collection_types import SimpleListModel
from tests.models.complex_types import OuterModel
from tests.models.simple_types import StrModel


class TestSetattrSimpleField(AsyncBenchmarkTest):
    models = {TTLMode.NO_TTL: StrModel}

    async def setup(self, mode):
        cls = self.models[mode]
        return cls(name="initial")

    async def action(self, model):
        model.name = "updated"


class TestSetattrListItem(AsyncBenchmarkTest):
    models = {TTLMode.NO_TTL: SimpleListModel}

    async def setup(self, mode):
        cls = self.models[mode]
        return cls(items=["initial"])

    async def action(self, model):
        model.items[0] = "updated"


class TestSetattrNestedField(AsyncBenchmarkTest):
    models = {TTLMode.NO_TTL: OuterModel}

    async def setup(self, mode):
        cls = self.models[mode]
        return cls()

    async def action(self, model):
        model.middle_model.tags = ["new"]
