import contextlib
import contextvars
import logging
from typing import Optional

from redis.asyncio.client import Pipeline
from redis.commands.json import JSON
from redis.exceptions import NoScriptError, ResponseError

from rapyer.errors import PersistentNoScriptError
from rapyer.scripts import registry as scripts_registry

logger = logging.getLogger("rapyer")

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


async def execute_pipeline_with_noscript_recovery(
    pipe: Pipeline, meta, ignore_redis_error: bool = False
) -> list:
    """Execute a queued pipeline, self-healing once on NoScriptError.

    On NOSCRIPT, re-register the scripts and replay ONLY the EVALSHA entries.
    In a transactional MULTI/EXEC a NOSCRIPT is an EXEC-time (runtime) error,
    not a queue-time EXECABORT: the other queued commands still execute and
    commit on the first attempt -- Redis does not roll back a transaction when
    one command errors mid-execution. Replaying the full stack would therefore
    re-apply the ride-along native commands (JSON.SET, and the non-idempotent
    JSON.NUMINCRBY / JSON.ARRAPPEND / special-field ops) a second time. Only the
    missing-script EVALSHA needs re-running; re-registering yields the same SHA
    for unchanged script text, so the backed-up EVALSHA args stay valid.

    The success path returns ``pipe.execute()``'s result unchanged -- this only
    adds exception branches, so it is behaviorally identical to a bare
    ``await pipe.execute()`` when no error occurs. ``ignore_redis_error`` mirrors
    ``_apipeline``: a non-NOSCRIPT ResponseError is swallowed (logged) instead of
    raised so both write paths share this single recovery implementation.
    """
    commands_backup = list(pipe.command_stack)
    try:
        return await pipe.execute()
    except NoScriptError:
        pass
    except ResponseError as exc:
        if not ignore_redis_error:
            raise
        logger.warning(
            "Swallowed ResponseError during pipeline.execute() with "
            "ignore_redis_error=True: %s",
            exc,
        )
        return []

    await scripts_registry.handle_noscript_error(meta.redis, meta)
    evalsha_commands = [
        (args, options) for args, options in commands_backup if args[0] == "EVALSHA"
    ]
    async with meta.redis.pipeline(transaction=True) as retry_pipe:
        for args, options in evalsha_commands:
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
