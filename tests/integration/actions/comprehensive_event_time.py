from abc import ABC

from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class ComprehensiveEventTimeOpBase(UpdateActionTestBase, ABC):
    """RedisDatetime ops on ``ComprehensiveTestModel.event_time``."""

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.event_time
