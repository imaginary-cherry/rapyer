from rapyer import AtomicRedisModel
from rapyer.actions import (
    ACTION_WRAPPER_SENTINEL,
    MARK_ACTION_PARAMS_ATTR,
    ActionGroup,
    install_action_for_meta,
)
from rapyer.config import RedisConfig
from rapyer.types.integer import RedisInt


def _count_action_wrappers(func):
    """
    Count action wrappers in the ``__wrapped__`` chain. Anything more than
    one means a previous install layer was stacked on top instead of peeled.
    """
    count = 0
    current = func
    while current is not None:
        if getattr(current, ACTION_WRAPPER_SENTINEL, False):
            count += 1
        current = getattr(current, "__wrapped__", None)
    return count


def test_inheriting_models_with_redis_int_keep_marks_redis_updated_wrapper():
    # Act
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

    # Assert - ``aload`` is READ: parent wraps, child peels (READ not in APPEND|ARITHMETIC).
    assert _count_action_wrappers(vars(PeelParentModel)["aload"]) == 1
    assert _count_action_wrappers(vars(PeelChildModel)["aload"]) == 0

    # ``aupdate`` is marked UPDATE: same contradiction as aload.
    assert _count_action_wrappers(vars(PeelParentModel)["aupdate"]) == 1
    assert _count_action_wrappers(vars(PeelChildModel)["aupdate"]) == 0

    # ``asave`` is UPDATE|CREATE: parent wraps on UPDATE, child's APPEND|ARITHMETIC peels.
    assert _count_action_wrappers(vars(PeelParentModel)["asave"]) == 1
    assert _count_action_wrappers(vars(PeelChildModel)["asave"]) == 0

    # ``aset_ttl`` has ignore_refresh=True, so it is never wrapped whatever the meta says.
    assert _count_action_wrappers(vars(PeelParentModel)["aset_ttl"]) == 0
    assert _count_action_wrappers(vars(PeelChildModel)["aset_ttl"]) == 0

    # The per-field RedisInt subclass is built once with parent meta and reused by the child.
    field_type = PeelParentModel.model_fields["counter"].annotation
    assert PeelChildModel.model_fields["counter"].annotation is field_type
    assert issubclass(field_type, RedisInt)

    # ``RedisType.asave`` (UPDATE) — wraps under parent meta.
    assert _count_action_wrappers(vars(field_type)["asave"]) == 1
    # ``RedisType.aload`` (READ) — wraps under parent meta.
    assert _count_action_wrappers(vars(field_type)["aload"]) == 1
    # ``RedisInt.aincrease`` (UPDATE|ARITHMETIC, async) — wraps via UPDATE match.
    assert _count_action_wrappers(vars(field_type)["aincrease"]) == 1

    # install must leave marks_redis_updated in place and add no action wrapper of its own.
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


def test_recursive_model_recurses_into_nested_atomic_model():
    # Act
    class Inner(AtomicRedisModel):
        Meta = RedisConfig(
            ttl=66,
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

    # Assert - pre-condition: bare on every level.
    assert _count_action_wrappers(vars(inner_counter_type)["asave"]) == 1

    assert Outer.Meta.ttl is None
    assert _count_action_wrappers(vars(inner_counter_type)["asave"]) == 1


def test_install_action_for_meta_returns_unmarked_func_unchanged():
    # A function with no MarkActionParams is not an action, so install returns it untouched.
    def plain():
        return 1

    assert install_action_for_meta(plain, RedisConfig()) is plain
