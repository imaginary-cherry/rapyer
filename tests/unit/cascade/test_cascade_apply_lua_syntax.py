import pytest

from rapyer.scripts.loader import _load_template


@pytest.mark.asyncio
async def test_cascade_apply_lua_is_syntactically_valid(fake_redis_client):
    text = _load_template("cascade", "apply")

    assert "--[[CASCADE_PLAN_TABLE]]" in text

    sha = await fake_redis_client.script_load(text)

    assert isinstance(sha, str)
    assert sha
