import contextlib
import contextvars
from typing import Optional

from redis.asyncio.client import Redis

# Create a context variable to store the context
_context_pipe: contextvars.ContextVar[Optional["Redis"]] = contextvars.ContextVar(
    "redis", default=None
)


@contextlib.contextmanager
def with_pipe_context(pipe: Redis):
    try:
        pipe_prev = _context_pipe.set(pipe)
        yield pipe
    finally:
        _context_pipe.reset(pipe_prev)
