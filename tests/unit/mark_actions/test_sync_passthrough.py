from rapyer.actions import ACTION_GROUPS_ATTR, ActionGroup, mark_actions


def test_sync_function_is_returned_unwrapped():
    # Arrange
    def original():
        return "ok"

    # Act
    decorated = mark_actions(ActionGroup.READ)(original)

    # Assert
    assert decorated is original
    assert getattr(decorated, ACTION_GROUPS_ATTR) == ActionGroup.READ


def test_sync_method_on_class_is_returned_unwrapped():
    # Arrange
    class _Holder:
        def do(self):
            return "ok"

    original = _Holder.do

    # Act
    _Holder.do = mark_actions(ActionGroup.UPDATE, ActionGroup.READ)(_Holder.do)

    # Assert
    assert _Holder.do is original
    assert (
        getattr(_Holder.do, ACTION_GROUPS_ATTR)
        == ActionGroup.UPDATE | ActionGroup.READ
    )


def test_async_with_ignore_refresh_is_returned_unwrapped():
    # Arrange
    async def original():
        return "ok"

    # Act
    decorated = mark_actions(ActionGroup.DELETE, ignore_refresh=True)(original)

    # Assert
    assert decorated is original
    assert getattr(decorated, ACTION_GROUPS_ATTR) == ActionGroup.DELETE


def test_async_without_ignore_refresh_is_wrapped():
    # Arrange
    async def original():
        return "ok"

    # Act
    decorated = mark_actions(ActionGroup.UPDATE)(original)

    # Assert
    assert decorated is not original
    # Both the inner method and the wrapper carry the action groups attribute,
    # so static coverage discovery (tests/conftest.py) finds them either way.
    assert getattr(decorated, ACTION_GROUPS_ATTR) == ActionGroup.UPDATE
    assert getattr(original, ACTION_GROUPS_ATTR) == ActionGroup.UPDATE


def test_combined_action_groups_or_merged_on_attr():
    # Arrange
    def original():
        return None

    # Act
    decorated = mark_actions(
        ActionGroup.READ, ActionGroup.UPDATE, ActionGroup.APPEND
    )(original)

    # Assert
    combined = getattr(decorated, ACTION_GROUPS_ATTR)
    assert ActionGroup.READ in combined
    assert ActionGroup.UPDATE in combined
    assert ActionGroup.APPEND in combined
