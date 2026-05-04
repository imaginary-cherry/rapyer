from rapyer import AtomicRedisModel
from rapyer.actions import ACTION_WRAPPER_SENTINEL, MARK_ACTION_PARAMS_ATTR, ActionGroup
from rapyer.config import RedisConfig
from rapyer.types.integer import RedisInt
from tests.build_helpers import recursive_build_redis_model


def _count_action_wrappers(func):
    """Count action wrappers in the ``__wrapped__`` chain. Anything more than
    one means a previous install layer was stacked on top instead of peeled."""
    count = 0
    current = func
    while current is not None:
        if getattr(current, ACTION_WRAPPER_SENTINEL, False):
            count += 1
        current = getattr(current, "__wrapped__", None)
    return count


def test_inheriting_models_with_redis_int_keep_marks_redis_updated_wrapper():
    # Arrange — contradicting configs: parent refreshes on UPDATE/READ, child
    # on APPEND/ARITHMETIC. Both keep ``ttl=60`` so refresh decisions actually
    # fire (``ttl=None`` would short-circuit ``should_refresh_for_action``).
    class PeelParentModel(AtomicRedisModel):
        Meta = RedisConfig(
            ttl=60,
            refresh_ttl=ActionGroup.UPDATE | ActionGroup.READ,
            init_with_rapyer=False,
        )
        counter: int = 0

    class PeelChildModel(PeelParentModel):
        Meta = RedisConfig(
            ttl=60,
            refresh_ttl=ActionGroup.APPEND | ActionGroup.ARITHMETIC,
            init_with_rapyer=False,
        )

    # Assert — pick a few representative methods and check wrap counts.

    # ``aload`` is marked READ: parent wraps, child peels (READ ∉ APPEND|ARITHMETIC).
    assert _count_action_wrappers(vars(PeelParentModel)["aload"]) == 1
    assert _count_action_wrappers(vars(PeelChildModel)["aload"]) == 0

    # ``aupdate`` is marked UPDATE: same contradiction as aload.
    assert _count_action_wrappers(vars(PeelParentModel)["aupdate"]) == 1
    assert _count_action_wrappers(vars(PeelChildModel)["aupdate"]) == 0

    # ``asave`` is UPDATE|CREATE with ``initial=True``. Both metas wrap (parent
    # via UPDATE match, child via initial+ttl). Wrap count must still be 1 on
    # the child — the install peeled parent's wrapper before re-wrapping.
    assert _count_action_wrappers(vars(PeelParentModel)["asave"]) == 1
    assert _count_action_wrappers(vars(PeelChildModel)["asave"]) == 1
    assert vars(PeelChildModel)["asave"] is not vars(PeelParentModel)["asave"]

    # ``aset_ttl`` carries ``ignore_refresh=True`` — never wrapped, regardless
    # of meta. If install ever stacked a wrapper here, count would be 1.
    assert _count_action_wrappers(vars(PeelParentModel)["aset_ttl"]) == 0
    assert _count_action_wrappers(vars(PeelChildModel)["aset_ttl"]) == 0

    # Per-field RedisInt subclass: built once with parent meta, reused by
    # child. The methods inherited from RedisType / BaseRedisType (``asave``,
    # ``aload``) and the RedisInt-specific async ``aincrease`` must all wrap
    # exactly once under parent's UPDATE|READ meta.
    field_type = PeelParentModel.model_fields["counter"].annotation
    assert PeelChildModel.model_fields["counter"].annotation is field_type
    assert issubclass(field_type, RedisInt)

    # ``RedisType.asave`` (UPDATE) — wraps under parent meta.
    assert _count_action_wrappers(vars(field_type)["asave"]) == 1
    # ``RedisType.aload`` (READ) — wraps under parent meta.
    assert _count_action_wrappers(vars(field_type)["aload"]) == 1
    # ``RedisInt.aincrease`` (UPDATE|ARITHMETIC, async) — wraps via UPDATE match.
    assert _count_action_wrappers(vars(field_type)["aincrease"]) == 1

    # Sync ``__iadd__`` / ``__isub__`` are wrapped with ``marks_redis_updated``.
    # install must leave them as that exact wrapper — no action wrapper added,
    # ``marks_redis_updated`` not stripped.
    for op_name in ("__iadd__", "__isub__"):
        redis_int_op = vars(RedisInt)[op_name]
        installed_op = vars(field_type)[op_name]
        assert installed_op is redis_int_op, (
            f"per-field {op_name} was replaced — peel-back stripped the "
            "marks_redis_updated wrapper."
        )
        assert _count_action_wrappers(installed_op) == 0
        assert hasattr(installed_op, MARK_ACTION_PARAMS_ATTR)
        assert hasattr(installed_op, "__wrapped__")


def test_recursive_build_redis_model_picks_up_runtime_meta_ttl_mutation():
    # Arrange — model has ``ttl=None`` at class-definition time, so the
    # per-field RedisInt subclass is built with the bare (unwrapped) methods.
    class RuntimeTtlModel(AtomicRedisModel):
        Meta = RedisConfig(
            ttl=None,
            refresh_ttl=ActionGroup.UPDATE,
            init_with_rapyer=False,
        )
        counter: int = 0

    field_type = RuntimeTtlModel.model_fields["counter"].annotation

    # Pre-condition — bare, no wrapper installed.
    assert _count_action_wrappers(vars(field_type)["asave"]) == 0
    assert _count_action_wrappers(vars(field_type)["aload"]) == 0
    assert _count_action_wrappers(vars(field_type)["aincrease"]) == 0

    # Act — mutate Meta at runtime then call the recursive helper.
    RuntimeTtlModel.Meta.ttl = 60
    recursive_build_redis_model(RuntimeTtlModel)

    # Assert — wrappers now applied to field methods whose action group
    # matches ``refresh_ttl`` (UPDATE).
    assert _count_action_wrappers(vars(field_type)["asave"]) == 1
    assert _count_action_wrappers(vars(field_type)["aincrease"]) == 1
    # READ doesn't match UPDATE-only refresh_ttl → still bare.
    assert _count_action_wrappers(vars(field_type)["aload"]) == 0

    # Act — revert ttl to None and rebuild.
    RuntimeTtlModel.Meta.ttl = None
    recursive_build_redis_model(RuntimeTtlModel)

    # Assert — wrappers peeled back to bare.
    assert _count_action_wrappers(vars(field_type)["asave"]) == 0
    assert _count_action_wrappers(vars(field_type)["aincrease"]) == 0
    assert _count_action_wrappers(vars(field_type)["aload"]) == 0


def test_recursive_build_redis_model_recurses_into_nested_atomic_model():
    # Arrange — both Outer and Inner start without TTL. The nested model gets
    # its own dynamic subclass with its own Meta when Outer is defined.
    class Inner(AtomicRedisModel):
        Meta = RedisConfig(
            ttl=None,
            refresh_ttl=ActionGroup.UPDATE,
            init_with_rapyer=False,
        )
        counter: int = 0

    class Outer(AtomicRedisModel):
        Meta = RedisConfig(
            ttl=None,
            refresh_ttl=ActionGroup.UPDATE,
            init_with_rapyer=False,
        )
        inner: Inner

    inner_dynamic = Outer.model_fields["inner"].annotation
    inner_counter_type = inner_dynamic.model_fields["counter"].annotation

    # Pre-condition — bare on every level.
    assert _count_action_wrappers(vars(inner_counter_type)["asave"]) == 0

    # Act — mutate ONLY Inner's Meta, then run recursive rebuild on Outer.
    # The recursion should pick up the inner model and rebuild its field types
    # against Inner's (now-TTLed) Meta, not Outer's.
    Inner.Meta.ttl = 60
    inner_dynamic.Meta.ttl = 60
    recursive_build_redis_model(Outer)

    # Assert — inner's per-field RedisInt got re-installed with TTL,
    # picked up via Inner's Meta (Outer's Meta is still ttl=None).
    assert Outer.Meta.ttl is None
    assert _count_action_wrappers(vars(inner_counter_type)["asave"]) == 1


def test_plain_build_redis_model_on_child_does_not_touch_parent_field_install():
    # Arrange — parent + child share a per-field type. Parent owns the field;
    # child only differs in Meta. ``cls.build_redis_model()`` (the model-only
    # rebuild) must not touch the shared field type — that's reserved for the
    # opt-in ``recursive_build_redis_model`` test helper.
    class OwnerModel(AtomicRedisModel):
        Meta = RedisConfig(
            ttl=60,
            refresh_ttl=ActionGroup.UPDATE,
            init_with_rapyer=False,
        )
        counter: int = 0

    class HeirModel(OwnerModel):
        Meta = RedisConfig(
            ttl=60,
            refresh_ttl=ActionGroup.READ,  # contradicts parent
            init_with_rapyer=False,
        )

    field_type = OwnerModel.model_fields["counter"].annotation
    assert HeirModel.model_fields["counter"].annotation is field_type

    # Pre-condition — installed under parent's UPDATE meta.
    assert _count_action_wrappers(vars(field_type)["asave"]) == 1
    assert _count_action_wrappers(vars(field_type)["aload"]) == 0

    # Act — child rebuilds via the model-only rebuild.
    HeirModel.build_redis_model()

    # Assert — parent's installation is untouched.
    assert _count_action_wrappers(vars(field_type)["asave"]) == 1
    assert _count_action_wrappers(vars(field_type)["aload"]) == 0
