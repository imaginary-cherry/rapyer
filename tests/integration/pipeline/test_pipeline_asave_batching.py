import pytest

from rapyer.base import AtomicRedisModel
from tests.integration.pipeline.pipeline_atomicity_base import RapyerPipelineBase
from tests.models.collection_types import ComprehensiveTestModel


# NOTE: complementary to TestPipelineModelAsave (which covers a single-model
# field update). This one exercises batching of multiple fresh-model asaves
# under the module-level ``rapyer.apipeline()`` context.
class TestRapyerPipelineAsaveBatching(RapyerPipelineBase):
    covered_method = AtomicRedisModel.asave

    def create_models(self):
        return [
            ComprehensiveTestModel(name="model1", counter=1, tags=["tag1"]),
            ComprehensiveTestModel(name="model2", counter=2, tags=["tag2"]),
            ComprehensiveTestModel(name="model3", counter=3, tags=["tag3"]),
        ]

    async def setup_data(self):
        # Don't pre-insert — the asave calls inside the pipeline are the subject.
        return self.create_models()

    async def perform_action(self, piped):
        for model in self.created_models:
            await model.asave()

    async def load_data(self):
        return tuple([await self.real_redis_client.exists(m.key) for m in self.created_models])

    def expected_before(self):
        return 0, 0, 0

    def expected_after(self):
        return 1, 1, 1


@pytest.mark.asyncio
async def test_nested_apipeline__inner_saves_on_exit__outer_saves_on_exit(
    real_redis_client,
):
    # Arrange
    outer_model = ComprehensiveTestModel(name="outer", counter=10, tags=["outer_tag"])
    inner_model = ComprehensiveTestModel(name="inner", counter=20, tags=["inner_tag"])
    await outer_model.asave()
    await inner_model.asave()

    # Act & Assert - nested pipelines
    async with outer_model.apipeline() as outer:
        outer.counter = 100
        outer.name = "outer_modified"

        async with inner_model.apipeline() as inner:
            inner.counter = 200
            inner.name = "inner_modified"

        # Assert - after inner pipeline exits, inner changes should be saved
        loaded_inner = await ComprehensiveTestModel.aget(inner_model.key)
        assert loaded_inner.counter == 200
        assert loaded_inner.name == "inner_modified"

        # Assert - outer changes should NOT be saved yet (still in outer pipeline)
        loaded_outer = await ComprehensiveTestModel.aget(outer_model.key)
        assert loaded_outer.counter == 10  # Still original
        assert loaded_outer.name == "outer"  # Still original

    # Assert - after outer pipeline exits, outer changes should be saved
    final_outer = await ComprehensiveTestModel.aget(outer_model.key)
    assert final_outer.counter == 100
    assert final_outer.name == "outer_modified"
