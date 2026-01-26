import pytest

from rapyer import AtomicRedisModel
from tests.models.simple_types import StrModel, IntModel
from tests.models.index_types import IndexTestModel, PersonModel, AddressModel


@pytest.fixture
def setup_fake_redis_for_models(fake_redis_client):
    original_clients = {}
    models = [
        StrModel,
        IntModel,
        IndexTestModel,
        PersonModel,
        AddressModel,
        AtomicRedisModel,
    ]
    for model in models:
        original_clients[model] = (model.Meta.redis, model.Meta.is_fake_redis)
        model.Meta.redis = fake_redis_client
        model.Meta.is_fake_redis = True
    yield
    for model, (original_redis, original_is_fake) in original_clients.items():
        model.Meta.redis = original_redis
        model.Meta.is_fake_redis = original_is_fake
