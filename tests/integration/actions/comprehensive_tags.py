from abc import ABC

from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class ComprehensiveTagsOpBase(UpdateActionTestBase, ABC):
    """List ops on ``ComprehensiveTestModel.tags``. Sync / pipeline-only actions."""

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.tags
