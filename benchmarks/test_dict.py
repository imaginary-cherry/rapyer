import pytest

from tests.models.collection_types import StrDictModel


@pytest.mark.benchmark
def test__dict_apop__sanity(benchmark, real_redis_client, event_loop):
    def setup():
        model = StrDictModel(metadata={"key": "value"})
        event_loop.run_until_complete(model.asave())
        return (model,), {}

    def run_sync(model):
        return event_loop.run_until_complete(model.metadata.apop("key"))

    result = benchmark.pedantic(run_sync, setup=setup, rounds=20)
    assert result == "value"
