import pytest
import pytest_asyncio

from tests.models.index_types import IndexTestModel


@pytest.fixture
def test_models():
    return [
        IndexTestModel(name="Alice", age=25, description="Engineer"),
        IndexTestModel(name="Bob", age=30, description="Manager"),
        IndexTestModel(name="Charlie", age=35, description="Designer"),
        IndexTestModel(name="David", age=40, description="Director"),
    ]


@pytest_asyncio.fixture
async def inserted_test_models(test_models):
    await IndexTestModel.ainsert(*test_models)
    return test_models


@pytest_asyncio.fixture
async def create_index(redis_client):
    await IndexTestModel.acreate_index()
    yield
    await IndexTestModel.adelete_index()
