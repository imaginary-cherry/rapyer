"""The process-wide list of rapyer models, kept out of base.py so any layer can read it."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rapyer.base import AtomicRedisModel

# Appended by AtomicRedisModel.__init_subclass__; init_rapyer() and the cascade planner read it.
REDIS_MODELS: list[type["AtomicRedisModel"]] = []
