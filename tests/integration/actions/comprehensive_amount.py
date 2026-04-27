from abc import ABC

from tests.integration.actions.update import UpdateActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class ComprehensiveAmountOpBase(UpdateActionTestBase, ABC):
    """RedisFloat binary ops on ``ComprehensiveTestModel.amount``. ``self.test_input`` is ``BinaryOpCase``."""

    def create_models(self):
        return [ComprehensiveTestModel(amount=self.test_input.initial)]

    async def load_data(self):
        loaded = await ComprehensiveTestModel.aget(self.created_models[0].key)
        return loaded.amount

    def expected_before(self):
        return self.test_input.initial

    def expected_after(self):
        return self.test_input.expected
