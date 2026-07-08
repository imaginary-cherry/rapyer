import contextlib
import contextvars
from typing import Optional

from redis.asyncio.client import Pipeline
from redis.commands.json import JSON
from redis.exceptions import NoScriptError

from rapyer.errors import PersistentNoScriptError
from rapyer.scripts import registry as scripts_registry

# Create a context variable to store the context
_context_pipe: contextvars.ContextVar[Optional["Pipeline"]] = contextvars.ContextVar(
    "redis", default=None
)
_context_pipe_json: contextvars.ContextVar[Optional["JSON"]] = contextvars.ContextVar(
    "redis_pipe_json", default=None
)


@contextlib.contextmanager
def with_pipe_context(pipe: Pipeline):
    pipe_prev = _context_pipe.set(pipe)
    json_prev = _context_pipe_json.set(None)
    try:
        yield pipe
    finally:
        _context_pipe_json.reset(json_prev)
        _context_pipe.reset(pipe_prev)


def get_pipe_json() -> Optional["JSON"]:
    """JSON commands client for the current pipeline (lazy + cached)."""
    json_client = _context_pipe_json.get()
    if json_client is not None:
        return json_client
    pipe = _context_pipe.get()
    if pipe is None:
        return None
    json_client = pipe.json()
    _context_pipe_json.set(json_client)
    return json_client


async def execute_pipeline_with_noscript_recovery(pipe: Pipeline, meta) -> list:
    """Execute a queued pipeline, self-healing once on NoScriptError.

    Backs up the FULL command stack before executing -- not just the
    EVALSHA entries -- because a pipeline built via ``ensure_pipeline``/
    ``pipeline_with_execution`` can carry ride-along commands (e.g. a
    cascade EVALSHA alongside a JSON.SET from ``asave()``); an EVALSHA-only
    replay (as ``_apipeline`` does for its own, different, use case) would
    silently drop those ride-along writes. Re-registering scripts yields
    the same SHA for unchanged script text, so the backed-up EVALSHA args
    stay valid on replay.

    The success path returns ``pipe.execute()``'s result unchanged -- this
    only adds an exception branch, so it is behaviorally identical to a
    bare ``await pipe.execute()`` when no NOSCRIPT error occurs.
    """
    commands_backup = list(pipe.command_stack)
    try:
        return await pipe.execute()
    except NoScriptError:
        pass

    await scripts_registry.handle_noscript_error(meta.redis, meta)
    async with meta.redis.pipeline(transaction=True) as retry_pipe:
        for args, options in commands_backup:
            retry_pipe.execute_command(*args, **options)
        try:
            return await retry_pipe.execute()
        except NoScriptError as e:
            raise PersistentNoScriptError(
                "NOSCRIPT error persisted after re-registering scripts. "
                "This indicates a server-side problem with Redis."
            ) from e


@contextlib.asynccontextmanager
async def ensure_pipeline(meta, should_execute: bool = True):
    """Yield existing pipeline from context, or create a new transactional one.

    If already inside an active pipeline context, yields that pipeline without
    creating a new one (the outer context owns execution). Otherwise, creates
    a new transactional pipeline, sets it in context, executes on exit.

    If ``should_execute`` is False and a new pipeline is created, the caller is
    responsible for invoking ``pipe.execute()`` themselves before the context
    exits (useful when the caller needs to inspect the execute results).
    """
    existing = _context_pipe.get()
    if existing is not None:
        yield existing
    else:
        async with meta.redis.pipeline(transaction=True) as pipe:
            with with_pipe_context(pipe):
                yield pipe
                if should_execute:
                    await execute_pipeline_with_noscript_recovery(pipe, meta)


@contextlib.asynccontextmanager
async def pipeline_with_execution(meta):
    async with meta.redis.pipeline(transaction=True) as pipe:
        yield pipe
        await execute_pipeline_with_noscript_recovery(pipe, meta)
