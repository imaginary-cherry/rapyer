import abc
from typing import ClassVar, Optional

from rapyer.scripts.loader import load_sf_load_snippet, load_sf_save_snippet
from rapyer.types.base import BaseRedisType

SPECIAL_FIELD_KEY_PREFIX = "__rapyer_special__"


class SpecialFieldType(BaseRedisType, abc.ABC):
    """
    Base for field types stored separately from the model's JSON dump.

    Special field types are saved under a separate Redis key derived from
    the parent model's key and the field path. Each subclass defines its
    own storage mechanism (e.g., Sorted Set, Stream, etc.).

    Methods use ``self.client`` which is pipeline-aware: when called inside
    an ``ensure_pipeline()`` context, operations are automatically batched.
    """

    LUA_SNIPPET_DIR: ClassVar[Optional[str]] = None

    @classmethod
    def special_field_key(cls, model_key: str, field_path: str) -> str:
        path = field_path
        clean_name = path.lstrip(".")
        return f"{SPECIAL_FIELD_KEY_PREFIX}:{model_key}:{clean_name}"

    @property
    def special_key(self) -> str:
        """
        Redis key for this field's separate data structure.

        Format: ``__rapyer_special__:{model_key}:{dotted_field_path}``
        e.g., ``__rapyer_special__:MyModel:abc123:tasks`` for a top-level field,
        ``__rapyer_special__:MyModel:abc123:inner.tasks`` for a nested one.
        """
        return self.special_field_key(self.key, self.field_path)

    @abc.abstractmethod
    async def asave_special(self):
        """
        Save this field's data to its separate Redis structure.

        Uses ``self.client`` which is pipeline-aware.
        """

    @abc.abstractmethod
    async def adelete_special(self):
        """
        Delete this field's separate Redis data.

        Uses ``self.client`` which is pipeline-aware.
        """

    @abc.abstractmethod
    async def aduplicate_special(self, target_special_key: str):
        """
        Copy this field's data to a new key for a duplicated model.

        The *read* must use ``self.redis`` (direct client) so the data is
        available immediately; the *write* should use ``self.client`` so it
        participates in any active pipeline.
        """

    @classmethod
    async def aprepare_many(cls, fields: list["SpecialFieldType"]) -> None:
        """Pre-``ensure_pipeline()`` batch materialization seam (D-07/D-08/EMBED-05).

        Ready a batch of same-``lua_type_name()`` fields for save/insert,
        before any pipeline opens. Default no-op, inherited unchanged by every
        existing SF subclass. ``RedisText`` overrides this to own its whole
        embedding strategy internally: filter to dirty fields, batch one
        ``aembed_many(...)`` per distinct vectorizer, then stash the result
        for ``asave_special()``/``lua_save_args()``.
        """

    def adopt_state_from(self, previous):
        """
        Carry per-instance bookkeeping forward when this field is reassigned.

        Default no-op. Override for SF types whose Python value is immutable, so
        reassignment builds a new instance and would otherwise drop the old
        instance's state.
        """

    @classmethod
    def lua_type_name(cls) -> str:
        """
        The type of scripts for this class for our lua scripts
        """
        return cls.LUA_SNIPPET_DIR or cls.__name__

    @classmethod
    def lua_save_snippet(cls) -> str:
        """
        Return a Lua *function literal* ``function(special_key, payload) ... end``.

        Default implementation reads ``rapyer/scripts/lua/sf/{LUA_SNIPPET_DIR}/save.lua``;
        subclasses that prefer to inline the Lua can override directly.
        """
        if cls.LUA_SNIPPET_DIR is None:
            raise NotImplementedError(
                f"{cls.__name__} must set LUA_SNIPPET_DIR or override "
                "lua_save_snippet to participate in aget_or_create."
            )
        return load_sf_save_snippet(cls.LUA_SNIPPET_DIR)

    @classmethod
    def lua_load_snippet(cls) -> str:
        """
        Return a Lua *function literal* ``function(special_key) ... end``.

        Default implementation reads ``rapyer/scripts/lua/sf/{LUA_SNIPPET_DIR}/load.lua``;
        subclasses that prefer to inline the Lua can override directly.
        """
        if cls.LUA_SNIPPET_DIR is None:
            raise NotImplementedError(
                f"{cls.__name__} must set LUA_SNIPPET_DIR or override "
                "lua_load_snippet to participate in aget_or_create."
            )
        return load_sf_load_snippet(cls.LUA_SNIPPET_DIR)

    def lua_save_args(self) -> list:
        """
        Per-instance save data appended to ``ARGV``, reaching the
        ``lua_save_snippet`` function as a base offset and a count.

        Values may be ``bytes``; ARGV is binary-safe, so nothing needs encoding.
        Defaults to empty for SF types whose save is a no-op (e.g.
        ``RedisPriorityQueue``). Override when save needs the in-memory value
        (e.g. ``RedisSet`` ships its members).
        """
        return []

    @classmethod
    def has_lua_load_output(cls) -> bool:
        """
        Whether ``lua_load_snippet`` produces a value to inject into the
        model dump on the found branch.

        Defaults to ``True``. Override to ``False`` for SF types whose load
        snippet always returns ``nil`` so the Python side knows not to expect
        a slot in the script's return tuple for this field.
        """
        return True

    def clone(self):
        return self.__class__()
