import asyncio
import logging
from typing import Optional, Set

logger = logging.getLogger(__name__)

# Maintain a strong reference to running background tasks to prevent garbage collection mid-execution
_background_tasks: Set[asyncio.Task] = set()


def create_logged_task(coro, *, name: Optional[str] = None) -> asyncio.Task:
    """
    Creates an asyncio task with an attached done callback to log any unhandled exceptions.
    Prevents silent failure of fire-and-forget background coroutines and retains strong references.
    """
    try:
        task = asyncio.create_task(coro, name=name) if name else asyncio.create_task(coro)
    except TypeError:
        task = asyncio.create_task(coro)

    _background_tasks.add(task)

    def _handle_task_result(t: asyncio.Task):
        _background_tasks.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            task_name = getattr(t, "get_name", lambda: "unnamed_task")()
            logger.error(f"Unhandled exception in background task '{task_name}': {exc}", exc_info=exc)

    task.add_done_callback(_handle_task_result)
    return task
