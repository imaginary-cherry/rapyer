import pytest

from rapyer.scripts.loader import _load_template


@pytest.mark.asyncio
async def test_cascade_apply_lua_is_syntactically_valid(fake_redis_client):
    # Act
    text = _load_template("cascade", "apply")

    # Assert
    assert "--[[CASCADE_PLAN_TABLE]]" not in text
    assert "cjson.decode(ARGV[5]" in text

    # Act
    sha = await fake_redis_client.script_load(text)

    # Assert
    assert isinstance(sha, str)
    assert sha
