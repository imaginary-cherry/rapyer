import pytest
import pytest_asyncio

from rapyer import init_rapyer
from tests.models.index_types import (
    IndexTestModel,
    UserIndexModel,
    PersonModel,
    AddressModel,
)
from tests.models.simple_types import StrModel


@pytest_asyncio.fixture(autouse=True)
async def clean_test_indexes(redis_client):
    # Get list of existing indexes before test
    try:
        # Use _list() to get all indexes - this is the internal Redis Search command
        index_list = await redis_client.execute_command("FT._LIST")
        existing_indexes = set(index_list)
    except Exception:
        # If no indexes exist or the command fails, start with an empty set
        existing_indexes = set()

    yield

    # After test: clean up only newly created indexes
    try:
        index_list = await redis_client.execute_command("FT._LIST")
        current_indexes = set(index_list)

        # Delete only indexes created during this test
        new_indexes = current_indexes - existing_indexes
        for index_name in new_indexes:
            try:
                await redis_client.execute_command("FT.DROPINDEX", index_name)
            except Exception:
                # Ignore errors when dropping indexes (might already be deleted)
                pass
    except Exception:
        # If cleanup fails, continue silently to avoid test interference
        pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["model", "expected_indexed_fields", "expected_non_indexed_fields"],
    [
        [
            IndexTestModel,
            {"$.name": "TEXT", "$.age": "NUMERIC"},
            ["description"],
        ],
        [
            UserIndexModel,
            # Fields from UserIndexModel only (inherited fields not included in same index)
            {"$.username": "TEXT"},
            ["email"],
        ],
        [
            PersonModel,
            # Only direct fields are indexed, nested model fields are in separate indexes
            {"$.name": "TEXT"},
            ["email"],  # email is a Key, not Index
        ],
        [
            AddressModel,
            # Nested model has its own index with its indexed fields
            {"$.street": "TEXT", "$.city": "TEXT"},
            [],
        ],
    ],
)
async def test_basic_index_creation(
    redis_client, model, expected_indexed_fields, expected_non_indexed_fields
):
    # Arrange & Act
    await init_rapyer(redis=redis_client)

    # Assert
    # Check index exists
    index_name = f"idx:{model.class_key_initials()}"
    info = await redis_client.ft(index_name).info()

    # Verify index was created
    assert info is not None, f"Index not created for {model.__name__}"

    # Extract field information from the index
    fields_in_index = {}
    for attr in info["attributes"]:
        field_name = attr[1]  # Field name
        field_type = attr[5]  # Field type
        fields_in_index[field_name] = field_type

    # Assert indexed fields are present with correct types
    for field_name, expected_type in expected_indexed_fields.items():
        assert (
            field_name in fields_in_index
        ), f"Field '{field_name}' not found in index for {model.__name__}"
        assert (
            fields_in_index[field_name] == expected_type
        ), f"Field '{field_name}' in {model.__name__} expected type '{expected_type}', got '{fields_in_index[field_name]}'"

    # Assert non-indexed fields are not in index
    for field_name in expected_non_indexed_fields:
        # Check if the field exists with JSON path prefix
        json_field_name = f"$.{field_name}"
        assert (
            json_field_name not in fields_in_index
        ), f"Non-indexed field '{field_name}' found in index for {model.__name__}"


@pytest.mark.asyncio
async def test_index_override_preserves_existing_data(redis_client, clean_test_indexes):
    # Arrange
    IndexTestModel.Meta.redis = redis_client

    # Create a manual index with different fields than what the model expects
    index_name = f"idx:{IndexTestModel.class_key_initials()}"
    await redis_client.execute_command(
        "FT.CREATE",
        index_name,
        "ON",
        "JSON",
        "PREFIX",
        "1",
        f"{IndexTestModel.class_key_initials()}:",
        "SCHEMA",
        "wrong_field",
        "TEXT",
        "another_field",
        "NUMERIC",
    )

    # Create and save some test models
    model1 = IndexTestModel(name="Alice", age=25, description="Test user 1")
    model2 = IndexTestModel(name="Bob", age=30, description="Test user 2")
    model3 = IndexTestModel(name="Charlie", age=35, description="Test user 3")

    await IndexTestModel.ainsert(model1, model2, model3)
    model_keys = [model1.key, model2.key, model3.key]

    # Act - Run init_rapyer to override the index
    await init_rapyer(redis=redis_client)

    # Assert - Check that index was properly overridden
    info = await redis_client.ft(index_name).info()

    # Extract field information from the new index
    fields_in_index = {}
    for attr in info["attributes"]:
        field_name = attr[1]  # Field name
        field_type = attr[5]  # Field type
        fields_in_index[field_name] = field_type

    # Verify the index now has the correct schema for IndexTestModel
    expected_fields = {"$.name": "TEXT", "$.age": "NUMERIC"}
    for field_name, expected_type in expected_fields.items():
        assert (
            field_name in fields_in_index
        ), f"Expected field '{field_name}' not found in overridden index"
        assert (
            fields_in_index[field_name] == expected_type
        ), f"Field '{field_name}' expected type '{expected_type}', got '{fields_in_index[field_name]}'"

    # Verify wrong fields are no longer in the index
    assert (
        "wrong_field" not in fields_in_index
    ), "Old wrong_field still exists in overridden index"
    assert (
        "another_field" not in fields_in_index
    ), "Old another_field still exists in overridden index"

    # Assert - Verify all saved models still exist in Redis
    for key in model_keys:
        exists = await redis_client.exists(key)
        assert exists == 1, f"Model with key {key} was lost after index override"


@pytest.mark.asyncio
async def test_index_override_false_preserves_existing_index(
    redis_client, clean_test_indexes
):
    """
    Test that when override_old_idx=False, existing index is preserved and not overridden.
    """
    # Arrange
    IndexTestModel.Meta.redis = redis_client

    # Create a manual index with different fields than what the model expects
    index_name = f"idx:{IndexTestModel.class_key_initials()}"
    await redis_client.execute_command(
        "FT.CREATE",
        index_name,
        "ON",
        "JSON",
        "PREFIX",
        "1",
        f"{IndexTestModel.class_key_initials()}:",
        "SCHEMA",
        "original_field",
        "TEXT",
        "preserved_field",
        "NUMERIC",
    )

    # Verify the original index exists and capture its schema
    original_info = await redis_client.ft(index_name).info()
    original_fields = {}
    for attr in original_info["attributes"]:
        field_name = attr[1]  # Field name
        field_type = attr[5]  # Field type
        original_fields[field_name] = field_type

    # Act
    await init_rapyer(redis=redis_client, override_old_idx=False)

    # Assert - Check that the original index was preserved
    current_info = await redis_client.ft(index_name).info()
    current_fields = {}
    for attr in current_info["attributes"]:
        field_name = attr[1]  # Field name
        field_type = attr[5]  # Field type
        current_fields[field_name] = field_type

    # Verify the index still has the original schema (not the model's expected schema)
    assert (
        current_fields == original_fields
    ), "Index schema changed despite override_old_idx=False"

    # Verify original fields are still present
    assert (
        "original_field" in current_fields
    ), "Original field was removed despite override_old_idx=False"
    assert (
        "preserved_field" in current_fields
    ), "Preserved field was removed despite override_old_idx=False"

    # Verify the model's expected fields are NOT in the index
    assert (
        "name" not in current_fields
    ), "Model field 'name' was added despite override_old_idx=False"
    assert (
        "age" not in current_fields
    ), "Model field 'age' was added despite override_old_idx=False"


@pytest.mark.asyncio
async def test_acreate_index_with_no_index_fields_sanity(redis_client):
    # Arrange
    StrModel.Meta.redis = redis_client

    # Act
    await StrModel.acreate_index()

    # Assert
    index_list = await redis_client.execute_command("FT._LIST")
    assert StrModel.index_name() not in index_list
