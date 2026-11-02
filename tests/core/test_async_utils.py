import asyncio
import logging
import pytest
from src.core.async_utils import create_logged_task, _background_tasks


@pytest.mark.asyncio
async def test_create_logged_task_success():
    executed = False

    async def sample_coro():
        nonlocal executed
        await asyncio.sleep(0.01)
        executed = True
        return 42

    task = create_logged_task(sample_coro(), name="test_success_task")
    assert task in _background_tasks
    await task
    assert executed is True
    # Verify task was discarded from strong reference set
    assert task not in _background_tasks


@pytest.mark.asyncio
async def test_create_logged_task_exception_logged(caplog):
    async def failing_coro():
        await asyncio.sleep(0.01)
        raise ValueError("Simulated background error")

    with caplog.at_level(logging.ERROR):
        task = create_logged_task(failing_coro(), name="test_fail_task")
        assert task in _background_tasks
        # Wait for task completion
        try:
            await task
        except ValueError:
            pass

    assert task not in _background_tasks
    assert any("Unhandled exception in background task 'test_fail_task': Simulated background error" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_create_logged_task_cancelled():
    async def sleep_coro():
        await asyncio.sleep(1.0)

    task = create_logged_task(sleep_coro(), name="test_cancel_task")
    assert task in _background_tasks
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert task not in _background_tasks
