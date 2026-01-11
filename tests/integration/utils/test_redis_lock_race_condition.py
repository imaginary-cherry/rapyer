import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pytest
from rapyer.utils.redis import acquire_lock
from redis.asyncio import Redis


@dataclass
class LockEvent:
    timestamp: datetime
    worker_name: str
    event_type: str  # "acquired", "released", "expired", "stolen"
    lock_token: Optional[str] = None


async def worker_with_new_lock(
    redis: Redis,
    worker_name: str,
    resource_key: str,
    work_duration: float,
    events: List[LockEvent],
    start_delay: float = 0,
):
    """Worker using the new (correct) lock implementation."""
    if start_delay > 0:
        await asyncio.sleep(start_delay)

    lock_key = f"{resource_key}:lock"

    async with acquire_lock(redis, resource_key) as lock:
        # The new lock returns the lock object, get its token
        token = lock.local.token if hasattr(lock.local, "token") else str(lock)

        events.append(
            LockEvent(
                timestamp=datetime.now(),
                worker_name=worker_name,
                event_type="acquired",
                lock_token=token,
            )
        )

        # Simulate work
        await asyncio.sleep(work_duration)

        # With proper implementation, lock should still be ours
        current_token = await redis.get(lock_key)
        if current_token and current_token == token:
            # Lock still held correctly
            pass
        else:
            events.append(
                LockEvent(
                    timestamp=datetime.now(),
                    worker_name=worker_name,
                    event_type="expired",
                    lock_token=token,
                )
            )

    events.append(
        LockEvent(
            timestamp=datetime.now(),
            worker_name=worker_name,
            event_type="released",
            lock_token=token,
        )
    )


@pytest.mark.asyncio
async def test_new_lock_handles_expiration_correctly(redis_client):
    """
    Test demonstrates that the new lock implementation handles the same scenario correctly.

    Scenario:
    - Worker A acquires lock for 8 seconds of work
    - Worker B starts after 4 seconds
    - Worker B waits until Worker A completes (no race condition)
    - Locks are properly managed with ownership verification
    """
    # Arrange
    resource_key = "test_resource_new"
    events = []

    # Act
    await asyncio.gather(
        worker_with_new_lock(
            redis_client,
            "WorkerA",
            resource_key,
            work_duration=8,
            events=events,
            start_delay=0,
        ),
        worker_with_new_lock(
            redis_client,
            "WorkerB",
            resource_key,
            work_duration=3,
            events=events,
            start_delay=4,
        ),
    )

    # Assert
    # Check that WorkerA's lock was NOT stolen
    worker_a_events = [e for e in events if e.worker_name == "WorkerA"]
    stolen_events = [e for e in worker_a_events if e.event_type == "stolen"]
    assert (
        len(stolen_events) == 0
    ), "No race condition should occur with new implementation"

    # Check that workers acquired locks sequentially
    acquired_events = [e for e in events if e.event_type == "acquired"]
    assert len(acquired_events) == 2, "Both workers should eventually acquire the lock"

    # Verify proper sequencing: WorkerB only acquires after WorkerA releases
    worker_a_released = next(
        (
            e
            for e in events
            if e.worker_name == "WorkerA" and e.event_type == "released"
        ),
        None,
    )
    worker_b_acquired = next(
        (
            e
            for e in events
            if e.worker_name == "WorkerB" and e.event_type == "acquired"
        ),
        None,
    )

    assert (
        worker_a_released and worker_b_acquired
    ), "Both workers should have completed their operations"
    assert (
        worker_a_released.timestamp < worker_b_acquired.timestamp
    ), "WorkerB should only acquire lock after WorkerA properly releases it"
