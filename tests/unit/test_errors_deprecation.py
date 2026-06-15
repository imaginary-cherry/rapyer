import pytest

import rapyer.errors as errors
from rapyer.errors import UnsupportedArgumentTypeError

# TODO - we should remove this in the 1.4.0 - this test backward compatiability code for coverage


def test_deprecated_alias_warns_and_returns_new_class():
    # Coverage: errors.__getattr__'s deprecated-alias branch — emits the
    # DeprecationWarning and returns the renamed class.
    # Act / Assert
    with pytest.warns(DeprecationWarning):
        aliased = errors.UnsupportArgumentTypeError

    assert aliased is UnsupportedArgumentTypeError


def test_unknown_attribute_still_raises_attribute_error():
    # Coverage: errors.__getattr__'s fallback `raise AttributeError` for any
    # name that is not the deprecated alias.
    # Act / Assert
    with pytest.raises(AttributeError):
        errors.ThisAttributeDoesNotExist
