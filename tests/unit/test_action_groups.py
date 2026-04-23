import pytest

from rapyer.actions import ACTION_GROUPS_ATTR, ActionGroup, should_refresh_for_action
from rapyer.config import RedisConfig
from rapyer.errors import InvalidRefreshTtlError

# --- should_refresh_for_action tests ---


@pytest.mark.parametrize(
    ["refresh_ttl", "action", "expected"],
    [
        [True, ActionGroup.READ, True],
        [True, ActionGroup.UPDATE, True],
        [True, ActionGroup.DELETE, True],
        [False, ActionGroup.READ, False],
        [False, ActionGroup.UPDATE, False],
        [ActionGroup.READ, ActionGroup.READ, True],
        [ActionGroup.READ, ActionGroup.UPDATE, False],
        [ActionGroup.READ | ActionGroup.UPDATE, ActionGroup.READ, True],
        [ActionGroup.READ | ActionGroup.UPDATE, ActionGroup.UPDATE, True],
        [ActionGroup.READ | ActionGroup.UPDATE, ActionGroup.DELETE, False],
        [ActionGroup.APPEND, ActionGroup.APPEND, True],
        [ActionGroup.APPEND, ActionGroup.UPDATE, False],
    ],
)
def test_should_refresh_for_action(refresh_ttl, action, expected):
    config = RedisConfig(ttl=60, refresh_ttl=refresh_ttl)
    assert should_refresh_for_action(config, action) == expected


def test_should_refresh_returns_false_when_no_ttl():
    config = RedisConfig(ttl=None, refresh_ttl=True)
    assert should_refresh_for_action(config, ActionGroup.READ) is False


# --- RedisConfig.refresh_ttl DELETE guard tests ---


@pytest.mark.parametrize(
    "refresh_ttl",
    [
        ActionGroup.DELETE,
        ActionGroup.READ | ActionGroup.DELETE,
        ActionGroup.all(),  # all() includes DELETE → rejected
    ],
)
def test_redis_config_rejects_delete_in_class_declaration(refresh_ttl):
    from rapyer import AtomicRedisModel

    with pytest.raises(InvalidRefreshTtlError):

        class _BadModel(AtomicRedisModel):
            Meta = RedisConfig(ttl=60, refresh_ttl=refresh_ttl)


@pytest.mark.parametrize(
    "refresh_ttl",
    [
        True,
        False,
        ActionGroup.READ,
        ActionGroup.ERASE,
        ActionGroup.READ | ActionGroup.UPDATE,
    ],
)
def test_redis_config_accepts_non_delete_refresh_ttl(refresh_ttl):
    RedisConfig(ttl=60, refresh_ttl=refresh_ttl)


# --- ActionGroup.all() tests ---


def test_action_group_all_includes_every_member():
    all_groups = ActionGroup.all()
    for member in ActionGroup:
        assert member in all_groups


def test_action_group_all_for_ttl_excludes_delete():
    ttl_groups = ActionGroup.all(for_ttl=True)
    assert ActionGroup.DELETE not in ttl_groups
    for member in ActionGroup:
        if member is not ActionGroup.DELETE:
            assert member in ttl_groups


def test_action_group_all_for_ttl_accepted_by_redis_config():
    # ActionGroup.all(for_ttl=True) excludes DELETE → must not raise
    RedisConfig(ttl=60, refresh_ttl=ActionGroup.all(for_ttl=True))


# --- Decorator _action_groups attribute tests ---


def test_mark_actions_sets_action_groups_on_method():
    from rapyer.types.integer import RedisInt

    assert hasattr(RedisInt.aincrease, ACTION_GROUPS_ATTR)
    assert ActionGroup.UPDATE in RedisInt.aincrease._action_groups
    assert ActionGroup.ARITHMETIC in RedisInt.aincrease._action_groups


def test_list_aappend_has_update_and_append_groups():
    from rapyer.types.lst import RedisList

    assert ActionGroup.UPDATE in RedisList.aappend._action_groups
    assert ActionGroup.APPEND in RedisList.aappend._action_groups


def test_dict_adel_item_has_update_and_erase_groups():
    from rapyer.types.dct import RedisDict

    # adel_item removes an item from the collection but keeps the model key → ERASE, not DELETE
    assert ActionGroup.UPDATE in RedisDict.adel_item._action_groups
    assert ActionGroup.ERASE in RedisDict.adel_item._action_groups


def test_priority_queue_apush_has_update_and_append_groups():
    from rapyer.types.priority_queue import RedisPriorityQueue

    assert ActionGroup.UPDATE in RedisPriorityQueue.apush._action_groups
    assert ActionGroup.APPEND in RedisPriorityQueue.apush._action_groups
