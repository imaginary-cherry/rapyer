import pytest

from rapyer import AtomicRedisModel
from rapyer.actions import ACTION_GROUPS_ATTR, ActionGroup, should_refresh_for_action
from rapyer.config import RedisConfig
from rapyer.errors import InvalidRefreshTtlError
from rapyer.types.dct import RedisDict
from rapyer.types.integer import RedisInt
from rapyer.types.lst import RedisList
from rapyer.types.priority_queue import RedisPriorityQueue

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
    # Arrange
    config = RedisConfig(ttl=60, refresh_ttl=refresh_ttl)

    # Act
    result = should_refresh_for_action(config, action)

    # Assert
    assert result == expected


def test_should_refresh_returns_false_when_no_ttl():
    # Arrange
    config = RedisConfig(ttl=None, refresh_ttl=True)

    # Act
    result = should_refresh_for_action(config, ActionGroup.READ)

    # Assert
    assert result is False


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
    # Arrange
    bad_refresh_ttl = refresh_ttl

    # Act / Assert
    with pytest.raises(InvalidRefreshTtlError):

        class _BadModel(AtomicRedisModel):
            Meta = RedisConfig(ttl=60, refresh_ttl=bad_refresh_ttl)


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
    # Arrange
    ttl = 60

    # Act
    config = RedisConfig(ttl=ttl, refresh_ttl=refresh_ttl)

    # Assert
    assert config.refresh_ttl == refresh_ttl


# --- ActionGroup.all() tests ---


def test_action_group_all_includes_every_member():
    # Arrange
    members = list(ActionGroup)

    # Act
    all_groups = ActionGroup.all()

    # Assert
    for member in members:
        assert member in all_groups


def test_action_group_all_for_ttl_excludes_delete():
    # Arrange
    members = list(ActionGroup)

    # Act
    ttl_groups = ActionGroup.all(for_ttl=True)

    # Assert
    assert ActionGroup.DELETE not in ttl_groups
    for member in members:
        if member is not ActionGroup.DELETE:
            assert member in ttl_groups


def test_action_group_all_for_ttl_accepted_by_redis_config():
    # Arrange
    refresh_ttl = ActionGroup.all(for_ttl=True)

    # Act
    config = RedisConfig(ttl=60, refresh_ttl=refresh_ttl)

    # Assert
    # ActionGroup.all(for_ttl=True) excludes DELETE → must not raise
    assert config.refresh_ttl == refresh_ttl


# --- Decorator _action_groups attribute tests ---


def test_mark_actions_sets_action_groups_on_method():
    # Arrange
    method = RedisInt.aincrease

    # Act
    action_groups = getattr(method, ACTION_GROUPS_ATTR)

    # Assert
    assert hasattr(method, ACTION_GROUPS_ATTR)
    assert ActionGroup.UPDATE in action_groups
    assert ActionGroup.ARITHMETIC in action_groups


def test_list_aappend_has_update_and_append_groups():
    # Arrange
    method = RedisList.aappend

    # Act
    action_groups = method._action_groups

    # Assert
    assert ActionGroup.UPDATE in action_groups
    assert ActionGroup.APPEND in action_groups


def test_dict_adel_item_has_update_and_erase_groups():
    # Arrange
    method = RedisDict.adel_item

    # Act
    action_groups = method._action_groups

    # Assert
    # adel_item removes an item from the collection but keeps the model key → ERASE, not DELETE
    assert ActionGroup.UPDATE in action_groups
    assert ActionGroup.ERASE in action_groups


def test_priority_queue_apush_has_update_and_append_groups():
    # Arrange
    method = RedisPriorityQueue.apush

    # Act
    action_groups = method._action_groups

    # Assert
    assert ActionGroup.UPDATE in action_groups
    assert ActionGroup.APPEND in action_groups
