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


@contextlib.asynccontextmanager
async def ensure_pipeline(meta):
    """Yield existing pipeline from context, or create a new transactional one.

    If already inside an active pipeline context, yields that pipeline without
    creating a new one (the outer context owns execution). Otherwise, creates
    a new transactional pipeline, sets it in context, executes on exit.
    """
    existing = _context_pipe.get()
    if existing is not None:
        yield existing
    else:
        async with meta.redis.pipeline(transaction=True) as pipe:
            with with_pipe_context(pipe):
                yield pipe
                await pipe.execute()
