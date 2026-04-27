from abc import ABC

from tests.integration.actions.ttl import TTLActionTestBase
from tests.models.collection_types import ComprehensiveTestModel


class TwoModelDeleteBase(TTLActionTestBase, ABC):
    """Two-model delete atomicity: model1 deleted, model2 preserved."""

    def create_models(self):
        return [
            ComprehensiveTestModel(tags=["tag1"], name="model1"),
            ComprehensiveTestModel(tags=["tag2"], name="model2"),
        ]

    async def load_data(self):
        model1, model2 = self.created_models
        return (
            await self.real_redis_client.exists(model1.key),
            await self.real_redis_client.exists(model2.key),
        )

    def expected_before(self):
        return 1, 1

    def expected_after(self):
        return 0, 1
