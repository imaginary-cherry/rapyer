import contextvars
from typing import Optional

from redis.asyncio.client import Redis

# Create a context variable to store the context
_context_var: contextvars.ContextVar[Optional["Redis"]] = contextvars.ContextVar(
    "redis", default=None
)
