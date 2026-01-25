import pytest

from tests.models.complex_types import InnerMostModel, MiddleModel, OuterModel
from tests.models.functionality_types import AllTypesModel
from tests.models.simple_types import FloatModel


class TestPipelineStringField:
    @pytest.mark.asyncio
    async def test_assignment_changes_persisted_after_pipeline_sanity(self):
        # Arrange
        model = AllTypesModel(str_field="initial")
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.str_field = "new_value"

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.str_field == "initial"

        # Assert - direct assignment is committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.str_field == "new_value"

    @pytest.mark.asyncio
    async def test_concatenation_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = AllTypesModel(str_field="base")
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.str_field += "_suffix"

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.str_field == "base"

        # Assert - changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.str_field == "base_suffix"

    @pytest.mark.asyncio
    async def test_multiple_updates_changes_preserved_during_pipeline_committed_after_edge_case(
        self,
    ):
        # Arrange
        model = AllTypesModel(str_field="start")
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.str_field += "_first"
            redis_model.str_field += "_second"

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.str_field == "start"

        # Assert - all accumulated changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.str_field == "start_first_second"


class TestPipelineIntegerField:
    @pytest.mark.asyncio
    async def test_assignment_changes_persisted_after_pipeline_sanity(self):
        # Arrange
        model = AllTypesModel(int_field=10)
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.int_field = 50

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.int_field == 10

        # Assert - direct assignment is committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.int_field == 50

    @pytest.mark.asyncio
    async def test_addition_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = AllTypesModel(int_field=100)
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.int_field += 25

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.int_field == 100

        # Assert - changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.int_field == 125

    @pytest.mark.asyncio
    async def test_multiple_operations_changes_preserved_during_pipeline_committed_after_edge_case(
        self,
    ):
        # Arrange
        model = AllTypesModel(int_field=50)
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.int_field += 10
            redis_model.int_field += 20

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.int_field == 50

        # Assert - all accumulated changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.int_field == 80


class TestPipelineListField:
    @pytest.mark.asyncio
    async def test_append_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = AllTypesModel()
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.list_field.append("item1")

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.list_field == []

        # Assert - changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.list_field == ["item1"]

    @pytest.mark.asyncio
    async def test_aappend_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = AllTypesModel()
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            await redis_model.list_field.aappend("async_item")

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.list_field == []

        # Assert - changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.list_field == ["async_item"]

    @pytest.mark.asyncio
    async def test_extend_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = AllTypesModel()
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.list_field.extend(["item1", "item2"])

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.list_field == []

        # Assert - changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.list_field == ["item1", "item2"]

    @pytest.mark.asyncio
    async def test_aextend_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = AllTypesModel()
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            await redis_model.list_field.aextend(["async_item1", "async_item2"])

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.list_field == []

        # Assert - changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.list_field == ["async_item1", "async_item2"]

    @pytest.mark.asyncio
    async def test_mixed_operations_changes_preserved_during_pipeline_committed_after_edge_case(
        self,
    ):
        # Arrange
        model = AllTypesModel()
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.list_field.append("sync_item")
            await redis_model.list_field.aappend("async_item")
            redis_model.list_field.extend(["extend1", "extend2"])

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.list_field == []

        # Assert - all changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert "sync_item" in final_model.list_field
        assert "async_item" in final_model.list_field
        assert "extend1" in final_model.list_field
        assert "extend2" in final_model.list_field


class TestPipelineDictField:
    @pytest.mark.asyncio
    async def test_update_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = AllTypesModel()
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.dict_field.update({"key1": "value1", "key2": "value2"})

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.dict_field == {}

        # Assert - changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.dict_field == {"key1": "value1", "key2": "value2"}

    @pytest.mark.asyncio
    async def test_aupdate_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = AllTypesModel()
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            await redis_model.dict_field.aupdate(
                async_key1="async_value1", async_key2="async_value2"
            )

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.dict_field == {}

        # Assert - changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.dict_field == {
            "async_key1": "async_value1",
            "async_key2": "async_value2",
        }

    @pytest.mark.asyncio
    async def test_setitem_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = AllTypesModel()
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.dict_field["direct_key"] = "direct_value"

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.dict_field == {}

        # Assert - changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.dict_field == {"direct_key": "direct_value"}

    @pytest.mark.asyncio
    async def test_aset_item_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = AllTypesModel()
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            await redis_model.dict_field.aset_item("async_key", "async_value")

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.dict_field == {}

        # Assert - changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.dict_field == {"async_key": "async_value"}

    @pytest.mark.asyncio
    async def test_mixed_operations_changes_preserved_during_pipeline_committed_after_edge_case(
        self,
    ):
        # Arrange
        model = AllTypesModel()
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.dict_field.update({"sync_key": "sync_value"})
            await redis_model.dict_field.aset_item("async_key", "async_value")
            redis_model.dict_field["direct_key"] = "direct_value"
            await redis_model.dict_field.aupdate(another_key="another_value")

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.dict_field == {}

        # Assert - all changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.dict_field["sync_key"] == "sync_value"
        assert final_model.dict_field["async_key"] == "async_value"
        assert final_model.dict_field["direct_key"] == "direct_value"
        assert final_model.dict_field["another_key"] == "another_value"


class TestPipelineBoolField:
    @pytest.mark.asyncio
    async def test_assignment_changes_persisted_after_pipeline_sanity(self):
        # Arrange
        model = AllTypesModel(bool_field=False)
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.bool_field = True

            # Assert - boolean changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.bool_field is False

        # Assert - boolean assignment is committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.bool_field is True


class TestPipelineFloatField:
    @pytest.mark.asyncio
    async def test_addition_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = FloatModel(value=10.5)
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.value += 5.25

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await FloatModel.aget(model.key)
            assert loaded_during_pipeline.value == 10.5

        # Assert - changes committed after pipeline
        final_model = await FloatModel.aget(model.key)
        assert final_model.value == 15.75

    @pytest.mark.asyncio
    async def test_subtraction_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = FloatModel(value=20.0)
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.value -= 7.5

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await FloatModel.aget(model.key)
            assert loaded_during_pipeline.value == 20.0

        # Assert - changes committed after pipeline
        final_model = await FloatModel.aget(model.key)
        assert final_model.value == 12.5

    @pytest.mark.asyncio
    async def test_multiplication_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = FloatModel(value=5.0)
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.value *= 3.0

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await FloatModel.aget(model.key)
            assert loaded_during_pipeline.value == 5.0

        # Assert - changes committed after pipeline
        final_model = await FloatModel.aget(model.key)
        assert final_model.value == 15.0

    @pytest.mark.asyncio
    async def test_division_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = FloatModel(value=100.0)
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.value /= 4.0

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await FloatModel.aget(model.key)
            assert loaded_during_pipeline.value == 100.0

        # Assert - changes committed after pipeline
        final_model = await FloatModel.aget(model.key)
        assert final_model.value == 25.0

    @pytest.mark.asyncio
    async def test_aincrease_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = FloatModel(value=50.0)
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            await redis_model.value.aincrease(10.5)

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await FloatModel.aget(model.key)
            assert loaded_during_pipeline.value == 50.0

        # Assert - changes committed after pipeline
        final_model = await FloatModel.aget(model.key)
        assert final_model.value == 60.5

    @pytest.mark.asyncio
    async def test_multiple_operations_changes_preserved_during_pipeline_committed_after_edge_case(
        self,
    ):
        # Arrange
        model = FloatModel(value=100.0)
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            redis_model.value += 50.0
            redis_model.value -= 25.0
            redis_model.value *= 2.0
            redis_model.value /= 5.0

            # Assert - changes not visible in Redis during pipeline
            loaded_during_pipeline = await FloatModel.aget(model.key)
            assert loaded_during_pipeline.value == 100.0

        # Assert - all accumulated changes committed after pipeline
        # (100 + 50 - 25) * 2 / 5 = 125 * 2 / 5 = 250 / 5 = 50
        final_model = await FloatModel.aget(model.key)
        assert final_model.value == 50.0


class TestPipelineCrossType:
    @pytest.mark.asyncio
    async def test_multiple_types_all_changes_preserved_during_pipeline_committed_after_sanity(
        self,
    ):
        # Arrange
        model = AllTypesModel(str_field="start", int_field=10)
        await model.asave()

        # Act
        async with model.apipeline() as redis_model:
            # String operations
            redis_model.str_field += "_modified"

            # Integer operations
            redis_model.int_field += 15

            # List operations
            await redis_model.list_field.aappend("list_item")
            redis_model.list_field.extend(["extend1", "extend2"])

            # Dict operations
            await redis_model.dict_field.aset_item("dict_key", "dict_value")
            redis_model.dict_field.update({"update_key": "update_value"})

            # Assert - all changes not visible in Redis during pipeline
            loaded_during_pipeline = await AllTypesModel.aget(model.key)
            assert loaded_during_pipeline.str_field == "start"
            assert loaded_during_pipeline.int_field == 10
            assert loaded_during_pipeline.list_field == []
            assert loaded_during_pipeline.dict_field == {}

        # Assert - all changes committed after pipeline
        final_model = await AllTypesModel.aget(model.key)
        assert final_model.str_field == "start_modified"
        assert final_model.int_field == 25
        assert "list_item" in final_model.list_field
        assert "extend1" in final_model.list_field
        assert "extend2" in final_model.list_field
        assert final_model.dict_field["dict_key"] == "dict_value"
        assert final_model.dict_field["update_key"] == "update_value"


class TestPipelineNestedModelField:
    @pytest.mark.asyncio
    async def test_assignment_changes_persisted_after_pipeline_sanity(self):
        # Arrange
        model = OuterModel()
        await model.asave()

        new_middle = MiddleModel(
            inner_model=InnerMostModel(lst=["new_item"], counter=99),
            tags=["new_tag"],
            metadata={"new_key": "new_value"},
        )

        # Act
        async with model.apipeline() as redis_model:
            redis_model.middle_model = new_middle

        # Assert
        final = await OuterModel.aget(model.key)
        assert final.middle_model.inner_model.lst == ["new_item"]
        assert final.middle_model.inner_model.counter == 99
        assert final.middle_model.tags == ["new_tag"]
        assert final.middle_model.metadata == {"new_key": "new_value"}
