import pytest

from rapyer.actions import ACTION_GROUPS_ATTR, ActionGroup, should_refresh_for_action
from rapyer.config import RedisConfig

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


# --- ActionGroup.all() tests ---


def test_action_group_all_includes_every_member():
    all_groups = ActionGroup.all()
    for member in ActionGroup:
        assert member in all_groups


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


def test_dict_adel_item_has_update_and_delete_groups():
    from rapyer.types.dct import RedisDict

    assert ActionGroup.UPDATE in RedisDict.adel_item._action_groups
    assert ActionGroup.DELETE in RedisDict.adel_item._action_groups


def test_priority_queue_apush_has_update_and_append_groups():
    from rapyer.types.priority_queue import RedisPriorityQueue

    assert ActionGroup.UPDATE in RedisPriorityQueue.apush._action_groups
    assert ActionGroup.APPEND in RedisPriorityQueue.apush._action_groups
