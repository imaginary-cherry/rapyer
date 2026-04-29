from rapyer.actions import (
    ACTION_GROUPS_ATTR,
    MARK_ACTION_PARAMS_ATTR,
    ActionGroup,
    mark_actions,
)


def test_sync_function_is_returned_unwrapped(mark_version):
    # Arrange
    def original():
        return "ok"

    # Act
    decorated = mark_actions(ActionGroup.READ, version=mark_version)(original)

    # Assert
    assert decorated is original
    assert getattr(decorated, ACTION_GROUPS_ATTR) == ActionGroup.READ


def test_sync_method_on_class_is_returned_unwrapped(mark_version):
    # Arrange
    class _Holder:
        def do(self):
            return "ok"

    original = _Holder.do

    # Act
    _Holder.do = mark_actions(
        ActionGroup.UPDATE, ActionGroup.READ, version=mark_version
    )(_Holder.do)

    # Assert
    assert _Holder.do is original
    assert (
        getattr(_Holder.do, ACTION_GROUPS_ATTR)
        == ActionGroup.UPDATE | ActionGroup.READ
    )


def test_async_with_ignore_refresh_is_returned_unwrapped(mark_version):
    # Arrange
    async def original():
        return "ok"

    # Act
    decorated = mark_actions(
        ActionGroup.DELETE, ignore_refresh=True, version=mark_version
    )(original)

    # Assert
    assert decorated is original
    assert getattr(decorated, ACTION_GROUPS_ATTR) == ActionGroup.DELETE


def test_async_without_ignore_refresh_decoration_shape(mark_version):
    """v1 wraps at decoration time; v2 returns the original and tags it for install."""
    # Arrange
    async def original():
        return "ok"

    # Act
    decorated = mark_actions(ActionGroup.UPDATE, version=mark_version)(original)

    # Assert: ACTION_GROUPS_ATTR is always set on the returned object.
    assert getattr(decorated, ACTION_GROUPS_ATTR) == ActionGroup.UPDATE
    assert getattr(original, ACTION_GROUPS_ATTR) == ActionGroup.UPDATE

    if mark_version == "v1":
        # v1 wraps async methods immediately.
        assert decorated is not original
    else:
        # v2 defers the wrap decision to install time — original is returned
        # and carries the params for `install_marked_action_methods` to consume.
        assert decorated is original
        assert hasattr(original, MARK_ACTION_PARAMS_ATTR)


def test_combined_action_groups_or_merged_on_attr(mark_version):
    # Arrange
    def original():
        return None

    # Act
    decorated = mark_actions(
        ActionGroup.READ, ActionGroup.UPDATE, ActionGroup.APPEND, version=mark_version
    )(original)

    # Assert
    combined = getattr(decorated, ACTION_GROUPS_ATTR)
    assert ActionGroup.READ in combined
    assert ActionGroup.UPDATE in combined
    assert ActionGroup.APPEND in combined
