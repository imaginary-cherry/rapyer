import pytest
import pytest_asyncio
from tests.models.common import Priority, TaskStatus
from tests.models.simple_types import TaskModel


@pytest_asyncio.fixture
async def redis_task_model(redis_client):
    TaskModel.Meta.redis = redis_client
    yield redis_client
    await redis_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["status", "priority"],
    [
        [TaskStatus.PENDING, Priority.LOW],
        [TaskStatus.RUNNING, Priority.MEDIUM],
        [TaskStatus.COMPLETED, Priority.HIGH],
        [TaskStatus.FAILED, Priority.LOW],
    ],
)
async def test_redis_enum_model_save_and_retrieve_sanity(
    redis_task_model, status, priority
):
    # Arrange
    task = TaskModel(name="test_task", status=status, priority=priority)

    # Act
    await task.asave()
    retrieved_task = await TaskModel.aget(task.key)

    # Assert
    assert retrieved_task.name == "test_task"
    assert retrieved_task.status == status
    assert retrieved_task.priority == priority
    assert retrieved_task.status.value == status.value
    assert retrieved_task.priority.value == priority.value
